from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate

from .check_consistency import Issue, normalize_issue_type

load_dotenv()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _get_world(story_state: Dict[str, Any]) -> Dict[str, Any]:
    w = story_state.get("world", {})
    return w if isinstance(w, dict) else {}


def _get_full_text(episode_facts: Dict[str, Any]) -> str:
    raw = episode_facts.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw
    return ""


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
    story_state: Dict[str, Any],
) -> List[Issue]:
    world = _get_world(story_state)
    full_text = _get_full_text(episode_facts)

    if not full_text.strip() or not world:
        return []

    llm = ChatUpstage(model="solar-pro")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """너는 ‘초보 작가를 돕는 웹소설 총괄 편집장’이다.

[판단 우선순위 규칙(최상위)]
- 이 시스템은 ‘사실관계(역사, 과학, 현실 지식)’보다 ‘세계관 설정’과 ‘등장인물 설정’을 항상 우선한다.
- 현실과 다르더라도 세계관/캐릭터 설정이 허용하면 오류가 아니다.

목표:
- [세계관 설정]과 [원고]를 비교해 독자가 “설정 충돌로 헷갈릴” 지점만 최소한으로 지적한다.
- 작가의 의도/문체/개성은 기본적으로 정상으로 간주한다.

판단 기준(중요):
1) world(세계관 오류)는 ‘명백한 설정 충돌’ + ‘본문에서 공개적으로 작동’ + ‘그런데도 자연스러운 반응/맥락이 없어 독자가 혼란’일 때만 잡아라.
2) 다음은 world 오류가 아니다: 주인공의 생각/내면독백/혼잣말, 높은 지식 수준, 현대적 비유/표현, 의도적 대비 연출.
3) “현대 용어가 있다”는 이유만으로 잡지 마라. (특히 내면 독백은 허용)
4) rewrite는 느낌을 바꾸지 말고   문제 표현만 최소 수정한다.

출력 규칙:
- 반드시 JSON만 출력
- 최상위 키: issues (리스트)
- 각 항목 필드: type, title, sentence, reason, rewrite, severity
- reason: 독자 관점에서 왜 혼란인지 1~2문장 (메타 발언 금지)
- sentence: 원문 그대로 짧게(120자 이내)
- rewrite: 최소 수정(180자 이내)
- severity: low|medium|high

주의:
- JSON 예시를 그대로 따라쓰지 말고, 필드만 맞춰서 출력해라.
"""),
        ("human", """[세계관 설정]
{world}

[원고]
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
            reason="규칙 엔진이 동작하지 않아 수정사항을 생성할 수 없습니다.",
            rewrite=f"LLM 호출/파싱 실패: {repr(e)}",
            severity="high",
        )]

    items = data.get("issues", [])
    if not isinstance(items, list):
        return []

    out: List[Issue] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        typ = normalize_issue_type(str(it.get("type", "world")))
        if typ != "world":
            typ = "world"

        title = str(it.get("title") or "세계관 수정 필요").strip()

        sentence = it.get("sentence")
        sentence = sentence.strip() if isinstance(sentence, str) and sentence.strip() else None

        reason = str(it.get("reason") or "").strip()
        rewrite = str(it.get("rewrite") or "").strip()

        severity = str(it.get("severity") or "medium").strip().lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"

        if not reason or not rewrite:
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
