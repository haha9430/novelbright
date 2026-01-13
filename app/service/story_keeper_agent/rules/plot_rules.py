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

    prompt = ChatPromptTemplate.from_messages([
        ("system", """너는 ‘초보 작가를 돕는 웹소설 총괄 편집장’이다.

[판단 우선순위 규칙(최상위)]
- 이 시스템은 ‘사실관계(역사, 과학, 현실 지식)’보다 ‘세계관 설정’과 ‘등장인물 설정’을 항상 우선한다.
- 현실과 다르더라도 세계관/캐릭터 설정이 허용하면 오류가 아니다.

목표:
- [이전 회차 기록]과 [이번 원고] 사이에서 독자가 “앞뒤가 안 맞는다/왜 이렇게 됐지”로 헷갈릴 지점만 지적한다.
- 외부 상식/고증으로 판단하지 않는다.
- 작가의 문체/개성은 건드리지 않는다.

판단 기준:
1) plot: 원인 없이 결과가 튀거나, 중요한 전환이 설명 없이 생겨 흐름이 끊기는 경우만.
2) continuity: 시간/상태/인물 인식/사건 순서가 앞 회차 기록과 명확히 충돌할 때만.
3) tone: 문체 교정 금지. 오직 “history에서 유지되던 서술 관점/호칭/핵심 표현”이 특별한 계기 없이 바뀌어 독자가 헷갈릴 때만.

출력 규칙:
- 반드시 JSON만 출력
- 최상위 키: issues (리스트)
- 각 항목 필드: type(plot|continuity|tone), title, sentence, reason, rewrite, severity
- reason: 독자 관점에서 왜 혼란인지 1~2문장 (메타 발언 금지)
- rewrite: 느낌 바꾸지 말고 최소 보정만
"""),
        ("human", """[이전 회차 기록]
{history}

[세계관 설정]
{world}

[이번 원고]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "history": json.dumps(history, ensure_ascii=False),
            "world": json.dumps(world, ensure_ascii=False),
            "full_text": full_text,
        })
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json(content) or {"issues": []}
    except Exception as e:
        return [Issue(
            type="plot",
            title="플롯 룰 검사 실패",
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

        typ = str(it.get("type") or "plot").strip().lower()
        if typ not in ("plot", "continuity", "tone"):
            typ = "plot"

        title = str(it.get("title") or "플롯 수정 필요").strip()

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
