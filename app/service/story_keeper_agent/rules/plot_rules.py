from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional as Opt

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

from .check_consistency import Issue, extract_original_sentence, pick_best_anchor

load_dotenv()

_CODEBLOCK_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_ISSUES_JSON_RE = re.compile(r'(\{[^{}]*"issues"\s*:\s*\[.*?\][^{}]*\})', re.DOTALL)
_ANY_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _safe_json_load(s: str) -> Opt[Dict[str, Any]]:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _extract_json(text: str) -> Opt[Dict[str, Any]]:
    if not isinstance(text, str):
        return None
    t = text.strip()

    m = _CODEBLOCK_JSON_RE.search(t)
    if m:
        obj = _safe_json_load(m.group(1))
        if obj is not None:
            return obj

    m = _ISSUES_JSON_RE.search(t)
    if m:
        obj = _safe_json_load(m.group(1))
        if obj is not None:
            return obj

    m = _ANY_JSON_RE.search(t)
    if m:
        obj = _safe_json_load(m.group(0))
        if obj is not None:
            return obj

    return None


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    return raw if isinstance(raw, str) and raw.strip() else ""


def _get_history(story_state: Dict[str, Any]) -> Dict[str, Any]:
    h = story_state.get("history", {})
    return h if isinstance(h, dict) else {}


def _is_leaf(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def _stringify(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _history_value_anchors(history: Dict[str, Any]) -> List[str]:
    anchors: List[str] = []

    for k in ("summary", "important_parts", "highlights", "key_points", "events"):
        v = history.get(k)
        if isinstance(v, list):
            for x in v[:40]:
                if _is_leaf(x):
                    s = _stringify(x)
                    if s and s != "null":
                        anchors.append(s)
        elif _is_leaf(v):
            s = _stringify(v)
            if s and s != "null":
                anchors.append(s)

    uniq: List[str] = []
    seen = set()
    for a in anchors:
        if a in seen:
            continue
        seen.add(a)
        uniq.append(a)

    return uniq[:160]


def _plot_value_anchors(plot_config: Dict[str, Any]) -> List[str]:
    anchors: List[str] = []
    if not isinstance(plot_config, dict):
        return anchors

    # plot.json에 있는 텍스트들을 앵커로 폭넓게 수집 (장르 상관없이)
    for k in (
        "summary",
        "important_parts",
        "theme",
        "premise",
        "constraints",
        "rules",
        "major_events",
        "forbidden",
        "must",
        "events",
        "highlights",
        "key_points",
    ):
        v = plot_config.get(k)
        if isinstance(v, list):
            for x in v[:80]:
                if _is_leaf(x):
                    s = _stringify(x)
                    if s and s != "null":
                        anchors.append(s)
        elif _is_leaf(v):
            s = _stringify(v)
            if s and s != "null":
                anchors.append(s)
        elif isinstance(v, dict):
            for vv in list(v.values())[:80]:
                if _is_leaf(vv):
                    s = _stringify(vv)
                    if s and s != "null":
                        anchors.append(s)

    uniq: List[str] = []
    seen = set()
    for a in anchors:
        if a in seen:
            continue
        seen.add(a)
        uniq.append(a)

    return uniq[:200]


def check_plot_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text:
        return []

    history = _get_history(story_state)

    anchors: List[str] = []
    anchors += _history_value_anchors(history)
    anchors += _plot_value_anchors(plot_config)

    if not anchors:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-플롯/연속성 비교기’다.
외부 상식/현실/역사/고증 판단은 절대 하지 않는다.
오직 anchors에 있는 문장과 원고 문장의 '정면 부정/배타 충돌'만 뽑는다.

[필수 규칙]
- 이슈를 만들 때, 어떤 anchor 문장과 충돌인지 anchor_sentence에 anchors에서 '그대로' 복붙해라.
- sentence는 원고에서 '그대로' 복붙해라.
- anchor_sentence가 anchors에 없으면 이슈를 만들지 마라.
- sentence가 원고에 없으면 이슈를 만들지 마라.
- 애매한 표현(가능/추측/비유/꿈/회상)은 제외.

[출력(JSON only)]
{{{{ "issues": [ {{{{
  "type": "plot|continuity",
  "title": "...",
  "anchor_sentence": "...",
  "sentence": "...",
  "reason": "...",
  "severity": "low|medium|high"
}}}} ] }}}}
없으면:
{{{{ "issues": [] }}}}
"""),
        ("human", """[anchors]
{anchors}

[manuscript]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "anchors": json.dumps(anchors, ensure_ascii=False),
            "full_text": full_text,
        })
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json(content) or {"issues": []}
    except Exception as e:
        return [Issue(
            type="plot",
            title="플롯 룰 검사 실패",
            sentence="(원고 전체)",
            reason=f"LLM 호출/파싱 실패: {repr(e)}",
            severity="high",
        )]

    out: List[Issue] = []
    items = data.get("issues", [])
    if not isinstance(items, list):
        items = []

    for it in items:
        if not isinstance(it, dict):
            continue

        # 1) anchor 검증 (장르필터 아님, 근거필터임)
        anchor_hint = str(it.get("anchor_sentence") or "").strip()
        anchor_norm = pick_best_anchor(anchors, anchor_hint)
        if not anchor_norm or anchor_norm not in anchors:
            continue

        # 2) 원문 sentence 강제
        hint_sentence = str(it.get("sentence") or "").strip()
        original_sentence = extract_original_sentence(full_text, hint_sentence)
        if not original_sentence:
            continue

        reason = str(it.get("reason") or "").strip()
        if not reason:
            continue

        sev = str(it.get("severity") or "medium").lower()
        if sev not in ("low", "medium", "high"):
            sev = "medium"

        t = str(it.get("type") or "plot").lower()
        if t not in ("plot", "continuity"):
            t = "plot"

        # title이 이상하게 '나이'로 가도 상관없음
        # 진짜 중요한 건 anchor_sentence + sentence 근거가 통과했냐임
        out.append(Issue(
            type=t,
            title=str(it.get("title") or "플롯/연속성 충돌"),
            sentence=original_sentence,
            reason=reason,
            severity=sev,
        ))

    return out
