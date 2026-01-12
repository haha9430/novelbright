from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .check_consistency import Issue

load_dotenv()


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw
    return ""


def _normalize_character_config(character_config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(character_config, dict):
        return {"characters": []}
    if isinstance(character_config.get("characters"), list):
        return {"characters": character_config["characters"]}
    profiles = character_config.get("profiles")
    if isinstance(profiles, dict):
        chars = []
        for name, data in profiles.items():
            if isinstance(data, dict):
                d = dict(data)
                d.setdefault("name", name)
                chars.append(d)
        return {"characters": chars}
    return {"characters": []}


def check_character_consistency(
    episode_facts: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text.strip():
        return []

    char_cfg = _normalize_character_config(character_config)
    if not char_cfg.get("characters"):
        return []

    llm = ChatUpstage(model="solar-pro")
    parser = JsonOutputParser()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 웹소설 캐릭터 일관성 검수자입니다.
[캐릭터 설정]과 [원고]를 비교해서 설정 충돌/표기 혼선만 반환하세요.
- 근거(evidence)는 원고에 있는 문장만 사용
- 없으면 빈 리스트

[출력 JSON]
{{"issues":[{{"type":"character","severity":"low|medium|high","title":"...","message":"...","evidence":"...","location":{{"hint":"..."}}, "rewrite":"...","reason":"..."}}]}}
"""),
        ("human", """[캐릭터 설정]
{characters}

[원고]
{full_text}
""")
    ])

    try:
        result = (prompt | llm | parser).invoke({
            "characters": json.dumps(char_cfg, ensure_ascii=False),
            "full_text": full_text
        })
    except Exception as e:
        err = f"LLM 호출/파싱 실패: {repr(e)}"
        return [Issue(
            type="character",
            severity="high",
            title="캐릭터 룰 검사 실패",
            message=err,
            evidence="(character_rules)",
            suggestion="",
            rewrite=err,
            reason="규칙 엔진이 동작하지 않아 수정사항을 생성할 수 없습니다.",
            location={"hint": "character_rules LLM 호출 실패"},
        )]

    items = result.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append(Issue(
            type="character",
            severity=str(it.get("severity", "low")),
            title=str(it.get("title", "캐릭터 수정 필요")),
            message=str(it.get("message", "")),
            evidence=it.get("evidence"),
            location=it.get("location") if isinstance(it.get("location"), dict) else None,
            rewrite=it.get("rewrite"),
            reason=it.get("reason"),
            suggestion=it.get("rewrite") or it.get("suggestion"),
        ))
    return out
