from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate

from .check_consistency import Issue

load_dotenv()

_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _get_world(story_state: Dict[str, Any]) -> Dict[str, Any]:
    w = story_state.get("world", {})
    return w if isinstance(w, dict) else {}


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw
    return ""


def _strip_codeblock(text: str) -> str:
    """LLM이 ```json ...``` 로 감싸도 JSON만 뽑아내기"""
    if not isinstance(text, str):
        return ""
    m = _CODEBLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _clip(s: Any, n: int) -> str:
    t = "" if s is None else str(s)
    t = " ".join(t.strip().split())
    return t if len(t) <= n else t[: n - 1] + "…"


def _extract_content(raw: Any) -> str:
    # langchain 반환 타입 대응
    if isinstance(raw, dict):
        return raw.get("content") or raw.get("text") or str(raw)
    return getattr(raw, "content", None) or getattr(raw, "text", None) or str(raw)


def check_world_consistency(
    episode_facts: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    world = _get_world(story_state)
    full_text = _get_full_text(episode_facts)

    # world 또는 원고가 비면 검사할 근거가 없으니 그대로 종료
    if not full_text.strip() or not world:
        return []

    # 필요하면 temperature=0으로 더 보수적으로
    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 웹소설 세계관 검수자입니다.

목표:
- [세계관 설정]과 [원고]를 비교하여 '확실한' 세계관 위반/누락만 찾습니다.
- 설정에 근거가 없는 추측/창작 금지.
- 근거(evidence)는 원고에서 발췌한 1문장 또는 1구절만(최대 120자).
- rewrite는 실제로 고칠 문장 1~2문장(최대 240자).
- reason은 설정의 어떤 키와 충돌하는지 명시(최대 200자).

반드시 아래 JSON만 출력하세요. 코드블록(```), 설명 문장 금지.

[출력 JSON]
{{
  "issues": [
    {{
      "rule_source": "world",
      "rule_id": "world_rules.magic_allowed",
      "severity": "low|medium|high",
      "evidence": "원고 근거(최대 120자)",
      "rewrite": "수정 제안(최대 240자)",
      "reason": "plot.json의 어떤 규칙과 충돌하는지(최대 200자)"
    }}
  ]
}}
"""),
        ("human", """[세계관 설정(JSON)]
{world}

[원고]
{full_text}
""")
    ])

    try:
        raw = (prompt | llm).invoke({
            "world": json.dumps(world, ensure_ascii=False),
            "full_text": full_text,
        })

        raw_text = _extract_content(raw)
        json_text = _strip_codeblock(raw_text)

        result = json.loads(json_text)
        if not isinstance(result, dict):
            raise ValueError(f"LLM JSON 최상위가 dict가 아님: {type(result)}")

    except Exception as e:
        err = f"LLM 호출/파싱 실패: {repr(e)}"
        return [Issue(
            type="world",
            severity="high",
            title="세계관 룰 검사 실패",
            message=err,
            evidence="(world_rules)",
            suggestion="",
            rewrite=err,
            reason="규칙 엔진이 동작하지 않아 수정사항을 생성할 수 없습니다.",
            location={"hint": "world_rules LLM 호출 실패"},
        )]

    items = result.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        rule_id = it.get("rule_id") or ""
        evidence = _clip(it.get("evidence"), 120)
        rewrite = _clip(it.get("rewrite"), 240)
        reason = _clip(it.get("reason"), 200)
        severity = str(it.get("severity", "low"))

        # “수정 피드백만” 원칙: rewrite/reason 없으면 스킵
        if not rewrite.strip() or not reason.strip():
            continue

        out.append(Issue(
            type="world",
            severity=severity if severity in ("low", "medium", "high") else "low",
            title="세계관 수정 필요",
            message="",
            evidence=evidence,
            location={"hint": evidence} if evidence else None,
            rewrite=rewrite,
            reason=f"[{rule_id}] {reason}" if rule_id else reason,
            suggestion=rewrite,
        ))

    return out
