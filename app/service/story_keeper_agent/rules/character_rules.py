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


def _normalize_character_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return {"characters": []}
    chars = cfg.get("characters")
    return {"characters": chars if isinstance(chars, list) else []}


def _pick_character_anchor_pool(character_config: Dict[str, Any]) -> List[str]:
    chars = character_config.get("characters", [])
    if not isinstance(chars, list):
        return []

    anchors: List[str] = []
    for i, ch in enumerate(chars[:12]):
        if not isinstance(ch, dict):
            continue

        name = ch.get("name")
        name_tag = str(name).strip() if isinstance(name, str) and name.strip() else f"idx{i}"

        # 성격/감정 태클 방지: 하드팩트 위주
        hard_keys = [
            "name", "gender", "age", "birth", "death", "is_alive",
            "injury", "missing_parts", "scar", "disability",
            "family", "parents", "siblings", "lover", "spouse",
            "rank", "status", "identity",
        ]

        picked = {}
        for k in hard_keys:
            if k in ch and _is_leaf(ch.get(k)):
                picked[k] = ch.get(k)

        if not picked:
            leaf_count = 0
            for k, v in ch.items():
                if leaf_count >= 10:
                    break
                if _is_leaf(v):
                    picked[k] = v
                    leaf_count += 1

        anchors += _build_anchors_from_json(picked, f"character[{name_tag}]")

    if len(anchors) > 160:
        anchors = anchors[:160]
    return anchors


def check_character_consistency(
    episode_facts: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    _ = story_state
    full_text = _get_full_text(episode_facts)
    if not full_text:
        return []

    cfg = _normalize_character_config(character_config)
    anchors = _pick_character_anchor_pool(cfg)
    if not anchors:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-캐릭터(JSON) 비교기’다.
외부 상식/현실/심리 추론을 절대 하지 않는다.

[판정]
- anchors를 "정면으로 뒤집는 경우"만 이슈 생성.
- JSON에 없는 정보는 오류 아님.
- 성격/기분/직업 디테일/병명 언급으로 태클 금지.
- 작가 의도/연출/서술순서/정보 은닉은 오류 아님.

[2차 검증]
- 없어서 오류면 버려라
- 단순 톤/감정 차이면 버려라
- 인물의 일시적 반응(화남/긴장 등)으로 태클이면 버려라

[reason(2줄 고정)]
json_anchor: "<충돌한 앵커 1줄 그대로>"
conflict: "<원고가 어떻게 정면으로 뒤집는지 1문장>"

[rewrite]
- 충돌만 제거하는 최소 수정 1문장

[출력(JSON only)]
{{ "issues": [ {{ "title","sentence","reason","rewrite","severity" }} ] }}
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
            type="character",
            title="캐릭터 룰 검사 실패",
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

        out.append(Issue(
            type="character",
            title=str(it.get("title") or "캐릭터 앵커 충돌"),
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=sev,
        ))

    return out
