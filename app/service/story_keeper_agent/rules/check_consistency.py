from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

TYPE_LABELS = {
    "world": "세계관 오류",
    "character": "캐릭터 설정 오류",
    "plot": "플롯 오류",
    "continuity": "연속성 오류",
}

REQUIRED_LINES = ["json_anchor:", "conflict:"]


@dataclass
class Issue:
    type: str
    title: str
    sentence: Optional[str]
    reason: str
    rewrite: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        t = self.type if self.type in TYPE_LABELS else "plot"
        return {
            "type": t,
            "label": TYPE_LABELS[t],
            "title": self.title,
            "sentence": self.sentence,
            "reason": self.reason,
            "rewrite": self.rewrite,
            "severity": self.severity,
        }


def _valid_reason_format(reason: str) -> bool:
    r = (reason or "").lower()
    return all(k in r for k in REQUIRED_LINES)


def _is_failure_issue(i: Issue) -> bool:
    # 그냥 title에 "검사 실패"면 실패로 취급
    return isinstance(i.title, str) and ("검사 실패" in i.title)


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
    issues += check_world_consistency(episode_facts, plot_config)
    issues += check_character_consistency(episode_facts, character_config, story_state)
    issues += check_plot_consistency(episode_facts, plot_config, story_state)

    final: List[Dict[str, Any]] = []
    for i in issues:
        # ✅ 실패 이슈는 일단 화면에 보이게
        if _is_failure_issue(i):
            # sentence가 None이면 최소값 채움
            if not i.sentence:
                i.sentence = "(원고 전체)"
            # reason 포맷도 최소 보장
            if not i.reason or not _valid_reason_format(i.reason):
                i.reason = "json_anchor: <none>\nconflict: 검사 실패"
            final.append(i.to_dict())
            continue

        # ✅ 정상 이슈는 엄격하게
        if not i.sentence:
            continue
        if not i.rewrite:
            continue
        if not _valid_reason_format(i.reason):
            continue
        final.append(i.to_dict())

    return final
