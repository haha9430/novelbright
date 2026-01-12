from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .check_consistency import Issue

load_dotenv()


def _get_world(story_state: Dict[str, Any]) -> Dict[str, Any]:
    w = story_state.get("world", {})
    return w if isinstance(w, dict) else {}


def _get_history(story_state: Dict[str, Any]) -> Dict[str, Any]:
    h = story_state.get("history", {})
    return h if isinstance(h, dict) else {}


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw
    return ""


def check_plot_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text.strip():
        return []

    world = _get_world(story_state)
    history = _get_history(story_state)

    llm = ChatUpstage(model="solar-pro")
    parser = JsonOutputParser()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 웹소설 플롯/연속성 검수자입니다.
[이전 회차 기록] + [세계관 설정] + [이번 원고]를 보고
인과/전환/연속성 문제가 있는 지점만 반환하세요.
- 근거(evidence)는 원고에 있는 문장만 사용
- 없으면 빈 리스트

[출력 JSON]
{{"issues":[{{"type":"plot|continuity","severity":"low|medium|high","title":"...","message":"...","evidence":"...","location":{{"hint":"..."}}, "rewrite":"...","reason":"..."}}]}}
"""),
        ("human", """[이전 회차 기록]
{history}

[세계관 설정]
{world}

[이번 원고]
{full_text}
""")
    ])

    try:
        result = (prompt | llm | parser).invoke({
            "history": json.dumps(history, ensure_ascii=False),
            "world": json.dumps(world, ensure_ascii=False),
            "full_text": full_text
        })
    except Exception as e:
        err = f"LLM 호출/파싱 실패: {repr(e)}"
        return [Issue(
            type="plot",
            severity="high",
            title="플롯 룰 검사 실패",
            message=err,
            evidence="(plot_rules)",
            suggestion="",
            rewrite=err,
            reason="규칙 엔진이 동작하지 않아 수정사항을 생성할 수 없습니다.",
            location={"hint": "plot_rules LLM 호출 실패"},
        )]

    items = result.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        typ = str(it.get("type", "plot"))
        if typ not in ("plot", "continuity"):
            typ = "plot"

        out.append(Issue(
            type=typ,
            severity=str(it.get("severity", "low")),
            title=str(it.get("title", "전개 수정 필요")),
            message=str(it.get("message", "")),
            evidence=it.get("evidence"),
            location=it.get("location") if isinstance(it.get("location"), dict) else None,
            rewrite=it.get("rewrite"),
            reason=it.get("reason"),
            suggestion=it.get("rewrite") or it.get("suggestion"),
        ))
    return out
