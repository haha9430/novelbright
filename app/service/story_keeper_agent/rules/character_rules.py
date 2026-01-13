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


def _normalize_character_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return {"characters": []}
    chars = cfg.get("characters")
    if isinstance(chars, list):
        return {"characters": chars}
    return {"characters": []}


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


def check_character_consistency(
    episode_facts: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Issue]:
    _ = story_state

    full_text = _get_full_text(episode_facts)
    if not full_text.strip():
        return []

    characters = _normalize_character_config(character_config)

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 ‘원고-캐릭터(JSON) 비교기’다.

✅ 핵심 원칙
- JSON에 없는 디테일은 “모름/열림”이다. 없다고 오류로 잡지 마라.
- 캐릭터는 모든 순간 한 성격만 가지지 않는다.
  성격/감정 표현을 “JSON에 없어서” 오류로 잡지 마라.

✅ 이슈로 잡아도 되는 “하드 앵커” 예시
- 이름/호칭/성별/나이(명시된 경우)/국적(명시된 경우)
- 신체 상태(왼팔 부상 등), 장애/흉터(명시된 경우)
- 사망/생존/실종 같은 상태(명시된 경우)
- 관계(가족/연인/원수 등) 가 명시됐는데 원고가 반대로 씀
- 특정 행동 금지/필수 같은 “명시적 제약” 위반

🚫 절대 잡지 말 것
- “JSON에 전문의/펠로우가 없으니 오류” (금지)
- 병명/전문분야 언급을 직업 불일치로 몰기 (금지)
- 성격 pros/cons가 none인데 감정표현했다고 오류 (금지)
- 그냥 디테일/설명/비유를 오류로 만들기 (금지)
- 외부 상식/현실 근거로 판단 (금지)

========================
🧷 issue 생성 조건 (필수)
========================
issue는 아래 3개가 모두 있어야 한다.
1) key_path: characters JSON의 경로
2) json_anchor: JSON에 적힌 하드 앵커 문장 그대로
3) manuscript_sentence: 원고 발췌 문장 그대로

conflict는 “앵커가 어떻게 뒤집혔는지”만 말한다.
“JSON에 없어서”라는 이유는 금지.

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
        ("human", """[characters_json]
{characters}

[manuscript]
{full_text}
"""),
    ])

    try:
        raw = (prompt | llm).invoke({
            "characters": json.dumps(characters, ensure_ascii=False),
            "full_text": full_text,
        })
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json(content) or {"issues": []}
    except Exception as e:
        return [Issue(
            type="character",
            title="캐릭터 룰 검사 실패",
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

        title = str(it.get("title") or "캐릭터 앵커 충돌").strip()

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
            type="character",
            title=title,
            sentence=sentence,
            reason=reason,
            rewrite=rewrite,
            severity=severity,
        ))

    return out
