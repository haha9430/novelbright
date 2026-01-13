# plot_rules.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional as Opt

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

from .check_consistency import Issue

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

    for vv in list(history.values())[:40]:
        if isinstance(vv, dict):
            for kk in ("summary", "important_parts"):
                x = vv.get(kk)
                if isinstance(x, list):
                    for it in x[:12]:
                        if _is_leaf(it):
                            s = _stringify(it)
                            if s and s != "null":
                                anchors.append(s)
                elif _is_leaf(x):
                    s = _stringify(x)
                    if s and s != "null":
                        anchors.append(s)

    uniq: List[str] = []
    seen = set()
    for a in anchors:
        if a in seen:
            continue
        seen.add(a)
        uniq.append(a)

    if len(uniq) > 160:
        uniq = uniq[:160]
    return uniq


def _plot_value_anchors(plot_config: Dict[str, Any]) -> List[str]:
    anchors: List[str] = []
    if not isinstance(plot_config, dict):
        return anchors

    for k in ("theme", "premise", "constraints", "rules", "major_events", "forbidden", "must"):
        v = plot_config.get(k)
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
        elif isinstance(v, dict):
            for vv in list(v.values())[:40]:
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

    if len(uniq) > 140:
        uniq = uniq[:140]
    return uniq


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

[금지]
- "anchors에 없어서 오류", "연결성", "고려/추론" 같은 말 금지.
- 배타적 충돌이 아니면 이슈를 만들지 마라.

[판정 기준]
- 정면 부정 또는 배타 충돌(동시에 성립 불가)이 원고에 확정 서술된 경우만 이슈.
- 애매한 표현(가능성/추측/비유/꿈/회상)은 오류로 잡지 말 것.
- anchors에 없는 정보는 오류 아님.

[출력(JSON only)]
{{ "issues": [ {{ "type": "plot|continuity", "title": "...", "sentence": "...", "reason": "...", "severity": "low|medium|high" }} ] }}
없으면:
{{ "issues": [] }}

[reason 작성]
- 사람이 읽는 문장 1~2줄.
- "이전 전개에서는 A인데 원고는 B로 확정이라 동시에 성립 불가" 형태만.
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

        sentence = it.get("sentence")
        sentence = sentence.strip() if isinstance(sentence, str) and sentence.strip() else None
        if not sentence:
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

        out.append(Issue(
            type=t,
            title=str(it.get("title") or "플롯/연속성 충돌"),
            sentence=sentence,
            reason=reason,
            severity=sev,
        ))

    return out
