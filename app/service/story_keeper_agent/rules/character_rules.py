# character_rules.py
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

        hard_keys = [
            "name", "age", "gender", "age_gender",
            "birth", "death", "is_alive",
            "job_status", "rank", "status", "identity",
            "injury", "missing_parts", "scar", "disability",
        ]

        picked = {}
        for k in hard_keys:
            if k in ch and _is_leaf(ch.get(k)):
                picked[k] = ch.get(k)

        if not picked:
            leaf_count = 0
            for k, v in ch.items():
                if leaf_count >= 8:
                    break
                if _is_leaf(v):
                    picked[k] = v
                    leaf_count += 1

        for k, v in picked.items():
            s = _stringify(v)
            if not s or s == "null":
                continue
            anchors.append(f"{name_tag} - {k}: {s}")

    if len(anchors) > 180:
        anchors = anchors[:180]
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
너는 ‘원고-캐릭터 설정 비교기’다.
외부 상식/현실/심리 추론은 절대 하지 않는다.
오직 anchors(캐릭터 확정 설정)와 원고만 본다.

[판정 기준]
- '정면 부정'뿐 아니라, 원고가 설정과 '서로 배타적인 다른 사실'을 확정적으로 말하면 이슈.
  예) 성별/나이/직업 상태/생사 같이 동시에 성립 불가한 값이 원고에서 확정될 때
- anchors에 없는 정보는 오류 아님.
- 성격/기분/말투/감정 묘사로 태클 금지.
- 애매한 표현(가능성/추측/비유/꿈/회상)은 오류로 잡지 말 것.

[출력(JSON only)]
{{ "issues": [ {{ "title": "...", "sentence": "...", "reason": "...", "severity": "low|medium|high" }} ] }}
없으면:
{{ "issues": [] }}

[reason 작성]
- 경로/키 같은 기술적 표기 쓰지 말고 사람이 읽는 문장으로.
- 1~2줄로: "설정에서는 A인데 원고 문장은 B로 확정 서술되어 충돌"
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
            type="character",
            title=str(it.get("title") or "캐릭터 설정 충돌"),
            sentence=sentence,
            reason=reason,
            severity=sev,
        ))

    return out
