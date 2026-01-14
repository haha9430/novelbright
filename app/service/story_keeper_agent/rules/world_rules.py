# world_rules.py
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


def _extract_world_from_plot(plot_config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plot_config, dict):
        return {}
    for k in ("world", "world_setting", "worldSettings", "settings", "setting", "global"):
        v = plot_config.get(k)
        if isinstance(v, dict) and v:
            return v
    return {}


def _is_leaf(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def _stringify(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _build_value_anchors(obj: Any) -> List[str]:
    anchors: List[str] = []

    def walk(x: Any):
        if _is_leaf(x):
            s = _stringify(x)
            if s and s != "null":
                anchors.append(s)
            return

        if isinstance(x, dict):
            for _, v in list(x.items())[:80]:
                walk(v)
            return

        if isinstance(x, list):
            for v in x[:80]:
                walk(v)
            return

    walk(obj)

    anchors = [a for a in anchors if isinstance(a, str) and a.strip()]
    if len(anchors) > 160:
        anchors = anchors[:160]
    return anchors


def check_world_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text:
        return []

    world = _extract_world_from_plot(plot_config)
    if not world:
        return []

    anchors = _build_value_anchors(world)
    if not anchors:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고 피드백 작성자’다. 오직 주어진 anchors(확정 사실)와 원고만 본다.
외부 상식/현실/역사/고증 판단은 절대 하지 않는다.

[이슈 생성 기준]
- 동시에 성립할 수 없는 ‘확정 서술’ 충돌만 이슈로 만든다.
- 애매한 표현(가능성/추측/비유/꿈/회상/과장)은 이슈로 만들지 마라.
- anchors에 없는 정보는 오류가 아니다.

[절대 금지 단어/표현]
- reason에서 아래 단어를 절대 쓰지 마라:
  anchors, 앵커, 설정, 기준, 룰, 판정, 비교, 명시, ~에서는, ~기준으로
- "anchors에 없어서 오류" 같은 말 금지.

[출력(JSON only)]
{{{{ "issues": [ {{ "title": "...", "sentence": "...", "reason": "...", "severity": "low|medium|high" }} ] }}}}
없으면:
{{{{ "issues": [] }}}}

[reason 작성 규칙]
- ‘작가에게 말하듯’ 자연어 1~2문장.
- “이 문장 때문에 독자가 무엇을 헷갈리는지 / 왜 동시에 성립이 어려운지”만 설명.
- 시스템 설명(설정/anchors/키/근거) 절대 언급하지 말 것.
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
            type="world",
            title="세계관 룰 검사 실패",
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

        out.append(Issue(
            type="world",
            title=str(it.get("title") or "세계관 충돌"),
            sentence=sentence,
            reason=reason,
            severity=sev,
        ))

    return out
