from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Issue:
    type: str  # "world" | "character" | "plot" | "continuity"
    severity: str  # "low" | "medium" | "high"
    title: str
    message: str
    evidence: Optional[str] = None
    suggestion: Optional[str] = None

    # 아래 3개는 edits 변환에 직접 쓰려고 추가
    location: Optional[Dict[str, Any]] = None  # {"hint": "...", "chunk_idx": 0}
    rewrite: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
        }
        if self.evidence is not None:
            out["evidence"] = self.evidence
        if self.suggestion is not None:
            out["suggestion"] = self.suggestion
        if self.location is not None:
            out["location"] = self.location
        if self.rewrite is not None:
            out["rewrite"] = self.rewrite
        if self.reason is not None:
            out["reason"] = self.reason
        return out


def _as_issue_list(items: Any) -> List[Issue]:
    if not isinstance(items, list):
        return []
    out: List[Issue] = []
    for it in items:
        if isinstance(it, Issue):
            out.append(it)
    return out


def check_consistency(
    episode_facts: Dict[str, Any],
    character_config: Dict[str, Any],
    plot_config: Dict[str, Any],
    story_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    world_rules / character_rules / plot_rules 결과를 합쳐서 issues[]로 반환
    """
    from .world_rules import check_world_consistency
    from .character_rules import check_character_consistency
    from .plot_rules import check_plot_consistency

    issues: List[Issue] = []

    issues += _as_issue_list(check_world_consistency(episode_facts, story_state))
    issues += _as_issue_list(check_character_consistency(episode_facts, character_config, story_state))
    issues += _as_issue_list(check_plot_consistency(episode_facts, plot_config, story_state))

    # 최종 반환은 dict list
    return [i.to_dict() for i in issues]
