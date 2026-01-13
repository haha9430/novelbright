from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate

from .check_consistency import Issue

load_dotenv()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw
    return ""


def _normalize_character_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return {"characters": []}
    chars = cfg.get("characters")
    if isinstance(chars, list):
        return {"characters": chars}
    return {"characters": []}


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not isinstance(text, str):
        return None
    m = _JSON_RE.search(text.strip())
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def check_character_consistency(
    episode_facts: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text.strip():
        return []

    characters = _normalize_character_config(character_config)

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """너는 ‘초보 작가를 돕는 웹소설 총괄 편집장’이다.

[판단 우선순위 규칙(최상위)]
- 이 시스템은 ‘사실관계(역사, 과학, 현실 지식)’보다 ‘세계관 설정’과 ‘등장인물 설정’을 항상 우선한다.
- 현실과 다르더라도 세계관/캐릭터 설정이 허용하면 오류가 아니다.

목표:
- [캐릭터 설정]과 [원고]를 비교해 독자가 “인물 이해가 흔들리거나 혼동”할 지점만 최소로 지적한다.
- 작가의 의도/말투/감정표현/개성은 기본적으로 정상으로 간주한다.

판단 기준(중요):
1) character 오류는 ‘핵심 정체성’이 무너질 때만 잡아라.
   - 한 번의 감정 변화/거친 말/농담/과장은 오류 아님.
   - 반복되거나, 캐릭터를 다른 사람처럼 보이게 만들 때만.

2) 이름/호칭:
   - 성 생략, 애칭, 호칭 변화는 기본 허용.
   - 오직 “다른 인물로 오해될 가능성”이 클 때만 지적.
   - 조사/어미 결합(A가/A는/A라면) 같은 건 지적 금지.

3) 외모/배경 설정 ‘누락’은 오류가 아니다. (작가 선택)
4) rewrite는 느낌/말투 바꾸지 말고 최소 수정만.
   - “대사를 추가해라/장면을 추가해라” 금지.
   - 혼동만 줄이는 수준으로만 고친다.

출력 규칙:
- 반드시 JSON만 출력
- 최상위 키: issues (리스트)
- 각 항목 필드: type(character), title, sentence, reason, rewrite, severity
- reason: 독자 관점에서 왜 혼동인지 1~2문장 (메타 발언 금지)
- sentence: 원문 그대로 짧게(120자 이내)
- rewrite: 최소 수정(180자 이내)
"""),
        ("human", """[캐릭터 설정]
{characters}

[원고]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "characters": json.dumps(characters, ensure_ascii=False),
            "full_text": full_text,
        })
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json(content) or {"issues": []}
    except Exception as e:
        return [Issue(
            type="character",
            title="캐릭터 룰 검사 실패",
            sentence=None,
            reason="규칙 엔진이 동작하지 않아 수정사항을 생성할 수 없습니다.",
            rewrite=f"LLM 호출/파싱 실패: {repr(e)}",
            severity="high",
        )]

    items = data.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        typ = str(it.get("type") or "character").strip().lower()
        if typ != "character":
            typ = "character"

        title = str(it.get("title") or "캐릭터 수정 필요").strip()

        sentence = it.get("sentence")
        sentence = sentence.strip() if isinstance(sentence, str) and sentence.strip() else None

        reason = str(it.get("reason") or "").strip()
        rewrite = str(it.get("rewrite") or "").strip()

        severity = str(it.get("severity") or "medium").strip().lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"

        if not reason or not rewrite:
            continue

        out.append(Issue(
            type=typ,
            title=title,
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=severity,
        ))

    return out
