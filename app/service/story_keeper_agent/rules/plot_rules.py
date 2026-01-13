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


def _is_leaf(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def _stringify(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _make_anchor_sentence(path: str, value: Any) -> str:
    return f"{path} = {_stringify(value)}"


def _build_anchors_from_json(obj: Any, prefix: str) -> List[str]:
    anchors: List[str] = []

    def walk(x: Any, p: str):
        if _is_leaf(x):
            anchors.append(_make_anchor_sentence(p, x))
            return

        if isinstance(x, dict):
            for k, v in x.items():
                if not isinstance(k, str):
                    continue
                nk = k.strip()
                if not nk:
                    continue
                walk(v, f"{p}.{nk}" if p else nk)
            return

        if isinstance(x, list):
            for idx, v in enumerate(x[:60]):
                if _is_leaf(v):
                    walk(v, f"{p}[{idx}]")
                elif isinstance(v, dict):
                    for kk in list(v.keys())[:12]:
                        vv = v.get(kk)
                        if _is_leaf(vv):
                            walk(vv, f"{p}[{idx}].{kk}")
            return

    walk(obj, prefix)
    return anchors


def _get_history(story_state: Dict[str, Any]) -> Dict[str, Any]:
    h = story_state.get("history", {})
    return h if isinstance(h, dict) else {}


def _pick_plot_anchor_pool(history: Dict[str, Any], plot_config: Dict[str, Any]) -> List[str]:
    anchors: List[str] = []
    anchors += _build_anchors_from_json(history, "history")

    if isinstance(plot_config, dict):
        small = {}
        for k in ("theme", "premise", "constraints", "rules", "major_events", "forbidden", "must"):
            v = plot_config.get(k)
            if v is not None:
                small[k] = v
        if small:
            anchors += _build_anchors_from_json(small, "plot")

    if len(anchors) > 200:
        anchors = anchors[:200]
    return anchors


def check_plot_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text:
        return []

    history = _get_history(story_state)
    anchors = _pick_plot_anchor_pool(history, plot_config)
    if not anchors:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-연속성/플롯(JSON) 비교기’다.
외부 상식/현실/역사/고증 판단을 절대 하지 않는다.

[판정]
- anchors를 정면으로 뒤집는 경우만 이슈 생성.
- JSON에 없는 정보는 오류 아님.
- 서술 순서/요약 차이는 오류 아님.
- 작가 의도에 대한 훈계/강요 금지.

[reason(2줄 고정)]
json_anchor: "<충돌한 앵커 1줄 그대로>"
conflict: "<원고가 어떻게 정면으로 뒤집는지 1문장>"

[rewrite]
- 충돌만 제거하는 최소 수정 1문장

[출력(JSON only)]
{{ "issues": [ {{ "type":"plot|continuity", "title","sentence","reason","rewrite","severity" }} ] }}
없으면:
{{ "issues": [] }}
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
            reason="json_anchor: <none>\nconflict: LLM 호출/파싱 실패",
            rewrite=repr(e),
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
        rewrite = str(it.get("rewrite") or "").strip()
        if not reason or not rewrite:
            continue

        sev = str(it.get("severity") or "medium").lower()
        if sev not in ("low", "medium", "high"):
            sev = "medium"

        t = str(it.get("type") or "plot").lower()
        if t not in ("plot", "continuity"):
            t = "plot"

        out.append(Issue(
            type=t,
            title=str(it.get("title") or "플롯/연속성 앵커 충돌"),
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=sev,
        ))

    return out
