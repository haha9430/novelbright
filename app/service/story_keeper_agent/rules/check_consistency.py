from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


TYPE_LABELS = {
    "world": "세계관 오류",
    "character": "캐릭터 설정 오류",
    "plot": "플롯 오류",
    "continuity": "연속성 오류",
}

REQUIRED_MARKERS = ["key_path:", "json_anchor:", "conflict:"]

# “없는걸 오류로 만들기” 패턴 컷
FORBIDDEN_PATTERNS = [
    "json에는", "json에", "없", "누락", "추가 필요", "관련 용어가 없음",
    "json에는 관련", "json에는 .* 없음", "json 정보가 없",
]

# 외부 사실/고증 끌고오면 컷
EXTERNAL_PATTERNS = [
    "현실", "역사", "고증", "과학", "시대", "실제로", "비현실", "당시",
    "실존", "제도", "관행", "원래", "사실관계",
]

# rewrite에 욕/과한 개입 막기(원치 않으면 더 추가 가능)
REWRITE_BANNED = ["시팔", "씨발", "ㅅㅂ", "fuck"]


def normalize_issue_type(t: str) -> str:
    t = (t or "").strip().lower()
    if t in TYPE_LABELS:
        return t
    return "plot"


@dataclass
class Issue:
    type: str
    title: str
    sentence: Optional[str]
    reason: str
    rewrite: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        nt = normalize_issue_type(self.type)
        return {
            "type": nt,
            "label": TYPE_LABELS.get(nt, "오류"),
            "title": self.title,
            "sentence": self.sentence,
            "reason": self.reason,
            "rewrite": self.rewrite,
            "severity": self.severity,
        }


def _as_issue_list(x: Any) -> List[Issue]:
    if x is None:
        return []
    if isinstance(x, list):
        return [i for i in x if isinstance(i, Issue)]
    if isinstance(x, Issue):
        return [x]
    return []


def _contains_any(text: str, patterns: List[str]) -> bool:
    low = (text or "").lower()
    for p in patterns:
        if p.lower() in low:
            return True
    return False


def _passes_policy(issue: Issue) -> bool:
    # 기본 필드
    if not issue.sentence or not str(issue.sentence).strip():
        return False
    if not issue.rewrite or not str(issue.rewrite).strip():
        return False

    r = (issue.reason or "").strip()
    if not all(m in r for m in REQUIRED_MARKERS):
        return False

    # “없는걸 오류” 패턴 컷
    if _contains_any(r, FORBIDDEN_PATTERNS):
        return False

    # 외부 고증/현실 컷
    if _contains_any(r, EXTERNAL_PATTERNS):
        return False

    # rewrite 과한 개입 컷
    if _contains_any(issue.rewrite, REWRITE_BANNED):
        return False

    return True


def check_consistency(
    *,
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    from .world_rules import check_world_consistency
    from .character_rules import check_character_consistency
    from .plot_rules import check_plot_consistency

    issues: List[Issue] = []
    issues += _as_issue_list(check_world_consistency(episode_facts, plot_config))
    issues += _as_issue_list(check_character_consistency(episode_facts, character_config, story_state))
    issues += _as_issue_list(check_plot_consistency(episode_facts, plot_config, story_state))

    # ✅ 마지막 검증: “확실한 앵커 충돌만” 남김
    issues = [i for i in issues if _passes_policy(i)]

    return [i.to_dict() for i in issues]
