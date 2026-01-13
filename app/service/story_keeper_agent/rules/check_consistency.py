# check_consistency.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

TYPE_LABELS = {
    "world": "세계관 오류",
    "character": "캐릭터 설정 오류",
    "plot": "플롯 오류",
    "continuity": "연속성 오류",
    "mixed": "복합 오류",
}


@dataclass
class Issue:
    type: str
    title: str
    sentence: Optional[str]
    reason: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        t = self.type if self.type in TYPE_LABELS else "plot"
        return {
            "type": t,
            "label": TYPE_LABELS[t],
            "title": self.title,
            "sentence": self.sentence,
            "reason": self.reason,
            "severity": self.severity,
        }


def _severity_rank(s: str) -> int:
    s = (s or "").lower()
    if s == "high":
        return 3
    if s == "medium":
        return 2
    if s == "low":
        return 1
    return 2


def _max_severity(a: str, b: str) -> str:
    return a if _severity_rank(a) >= _severity_rank(b) else b


def _is_failure_issue(i: Issue) -> bool:
    return isinstance(i.title, str) and ("검사 실패" in i.title)


def _merge_same_sentence(issues: List[Issue]) -> List[Issue]:
    buckets: Dict[str, List[Issue]] = {}
    for it in issues:
        if not it.sentence:
            continue
        key = it.sentence.strip()
        if not key:
            continue
        buckets.setdefault(key, []).append(it)

    merged: List[Issue] = []
    for sentence, items in buckets.items():
        if len(items) == 1:
            merged.append(items[0])
            continue

        type_set: List[str] = []
        for x in items:
            t = x.type if x.type in TYPE_LABELS else "plot"
            if t not in type_set:
                type_set.append(t)

        title = " + ".join(TYPE_LABELS[t] for t in type_set) if type_set else "복합 오류"

        reasons: List[str] = []
        for x in items:
            r = (x.reason or "").strip()
            if not r:
                continue
            if r not in reasons:
                reasons.append(r)

        if not reasons:
            reason = "원고의 해당 문장이 설정/연속성과 충돌합니다."
        else:
            keep = reasons[:3]
            if len(reasons) > 3:
                keep.append("추가 충돌도 발견되어 요약했습니다.")
            reason = "\n".join(keep)

        sev = "low"
        for x in items:
            sev = _max_severity(sev, x.severity)

        merged.append(Issue(
            type="mixed",
            title=title,
            sentence=sentence,
            reason=reason,
            severity=sev,
        ))

    return merged


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

    alive: List[Issue] = []
    for i in issues:
        if _is_failure_issue(i):
            if not i.sentence:
                i.sentence = "(원고 전체)"
            if not i.reason:
                i.reason = "룰 엔진이 정상적으로 결과를 만들지 못했습니다."
            alive.append(i)
            continue

        if not i.sentence:
            continue
        if not i.reason:
            continue
        alive.append(i)

    merged = _merge_same_sentence(alive)
    return [x.to_dict() for x in merged]
