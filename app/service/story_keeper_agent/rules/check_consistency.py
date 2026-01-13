from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


TYPE_LABELS = {
    "world": "세계관 오류",
    "character": "캐릭터 설정 오류",
    "plot": "플롯 오류",
    "continuity": "연속성 오류",
    "tone": "톤/문체 오류",
}


def normalize_issue_type(t: str) -> str:
    t = (t or "").strip().lower()
    if t in TYPE_LABELS:
        return t
    return "plot"


@dataclass
class Issue:
    type: str
    title: str
    reason: str
    rewrite: str
    sentence: Optional[str] = None
    severity: str = "medium"  # low|medium|high

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": normalize_issue_type(self.type),
            "title": self.title,
            "reason": self.reason,
            "rewrite": self.rewrite,
            "sentence": self.sentence,
            "severity": self.severity,
        }


def _as_issue_list(x: Any) -> List[Issue]:
    if x is None:
        return []
    if isinstance(x, list):
        return [it for it in x if isinstance(it, Issue)]
    if isinstance(x, Issue):
        return [x]
    return []


def check_consistency(
    episode_facts: Dict[str, Any],
    plot_config: Dict[str, Any],
    character_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    from .world_rules import check_world_consistency
    from .character_rules import check_character_consistency
    from .plot_rules import check_plot_consistency

    issues: List[Issue] = []
    issues += _as_issue_list(check_world_consistency(episode_facts, story_state))
    issues += _as_issue_list(check_character_consistency(episode_facts, character_config, story_state))
    issues += _as_issue_list(check_plot_consistency(episode_facts, plot_config, story_state))

    return [i.to_dict() for i in issues]
