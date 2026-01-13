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


def _extract_world_from_plot(plot_config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plot_config, dict):
        return {}
    for k in ("world", "world_setting", "worldSettings", "settings", "setting", "global"):
        v = plot_config.get(k)
        if isinstance(v, dict) and v:
            return v
    return plot_config if isinstance(plot_config, dict) else {}


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


def check_world_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
) -> List[Issue]:
    full_text = _get_full_text(episode_facts)
    if not full_text.strip():
        return []

    world = _extract_world_from_plot(plot_config)
    if not isinstance(world, dict) or not world:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-세계관(JSON) 비교기’다.

✅ 핵심 원칙
- JSON은 “전부”가 아니라 “앵커(확정/제약)”만 들어있는 기준이다.
- JSON에 ‘없다’는 것은 “모름/열림”이다.
- 따라서 JSON에 없는 정보를 원고가 말해도 오류가 아니다.

✅ 이슈로 잡아도 되는 것(앵커 충돌만)
- JSON이 명시적으로 “확정”한 사실을 원고가 뒤집음
- JSON이 명시적으로 “금지/불가/불가능/절대”로 제한한 것을 원고가 실행
- JSON이 명시적으로 “반드시/항상/오직”이라고 규정한 것을 원고가 위반

🚫 절대 잡지 말 것
- “JSON에 없으니 오류” (금지)
- 현실/역사/고증/과학/상식 기반 판단 (금지)
- 작가 의도/문장 자연스러움 평가 (금지)
- 디테일 추가(직업 용어, 병명, 배경 설명) 자체를 오류로 만들기 (금지)

========================
🧷 issue 생성 조건 (필수)
========================
issue는 아래 3개가 모두 있어야 생성한다.
1) key_path: JSON 경로
2) json_anchor: JSON에 실제로 적힌 ‘확정/제약’ 문장 그대로
3) manuscript_sentence: 원고에서 발췌한 문장 그대로

그리고 conflict는 “앵커를 어떻게 위반했는지”만 1문장으로 말한다.
외부 사실/고증 언급하면 즉시 삭제.

========================
📤 출력 (JSON만)
========================
{{
  "issues": [
    {{
      "title": "짧은 제목",
      "sentence": "원고 발췌(필수)",
      "reason": "key_path: ...\\njson_anchor: ...\\nconflict: ...",
      "rewrite": "앵커 위반만 제거한 최소 수정 문장(필수)",
      "severity": "low|medium|high"
    }}
  ]
}}

issues 없으면 {{ "issues": [] }} 만 출력.
"""),
        ("human", """[world_json]
{world}

[manuscript]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "world": json.dumps(world, ensure_ascii=False),
            "full_text": full_text,
        })
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json(content) or {"issues": []}
    except Exception as e:
        return [Issue(
            type="world",
            title="세계관 룰 검사 실패",
            sentence=None,
            reason="LLM 호출/파싱 실패",
            rewrite=f"{repr(e)}",
            severity="high",
        )]

    items = data.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        title = str(it.get("title") or "세계관 앵커 충돌").strip()

        sentence = it.get("sentence")
        sentence = sentence if isinstance(sentence, str) else ""
        sentence = sentence.strip() or None

        reason = str(it.get("reason") or "").strip()
        rewrite = str(it.get("rewrite") or "").strip()

        severity = str(it.get("severity") or "medium").strip().lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"

        if not sentence or not reason or not rewrite:
            continue

        out.append(Issue(
            type="world",
            title=title,
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=severity,
        ))

    return out
