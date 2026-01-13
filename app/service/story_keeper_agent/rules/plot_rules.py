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


def _get_history(story_state: Dict[str, Any]) -> Dict[str, Any]:
    h = story_state.get("history", {})
    return h if isinstance(h, dict) else {}


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
    return {}


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

    history = _get_history(story_state)
    world = _extract_world_from_plot(plot_config)

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-이전흐름/플롯(JSON) 비교기’다.

✅ 핵심 원칙
- JSON(스토리 히스토리/플롯)에 없는 것은 “모름/열림”이다.
- 요약/히스토리의 표현이 다르다고 다 오류가 아니다.
- 오직 “확정된 사건/상태”가 뒤집힐 때만 잡는다.

✅ 이슈로 잡아도 되는 것
- 이전화에서 확정된 사건이 원고에서 반대로 서술됨
  (예: A가 죽었다 → 원고에서 생존)
- 특정 인물 관계/소유/장소가 확정인데 원고가 뒤집음
- 플롯에서 “반드시/절대/금지/오직” 같은 제약 위반

🚫 금지
- “디테일이 다르다” 수준(요약 방식 차이) 태클
- 현실/고증/상식 근거
- 작가 의도/문장 평가

========================
🧷 issue 조건 (필수)
========================
1) key_path: plot/history JSON의 경로
2) json_anchor: JSON에 적힌 확정 문장 그대로
3) manuscript_sentence: 원고 발췌 그대로

========================
📤 출력 (JSON만)
========================
{{
  "issues": [
    {{
      "type": "plot|continuity",
      "title": "짧은 제목",
      "sentence": "원고 발췌(필수)",
      "reason": "key_path: ...\\njson_anchor: ...\\nconflict: ...",
      "rewrite": "앵커 위반만 제거한 최소 수정(필수)",
      "severity": "low|medium|high"
    }}
  ]
}}

issues 없으면 {{ "issues": [] }}.
"""),
        ("human", """[story_history_json]
{history}

[plot_json]
{plot_config}

[world_json]
{world}

[manuscript]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "history": json.dumps(history, ensure_ascii=False),
            "plot_config": json.dumps(plot_config, ensure_ascii=False),
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

        typ = str(it.get("type") or "plot").strip().lower()
        if typ not in ("plot", "continuity"):
            typ = "plot"

        title = str(it.get("title") or "플롯/연속성 앵커 충돌").strip()

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
            type=typ,
            title=title,
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=severity,
        ))

    return out
