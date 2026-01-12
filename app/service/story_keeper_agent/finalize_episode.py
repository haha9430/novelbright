from __future__ import annotations
from typing import Any, Dict, List


def issues_to_edits(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    issues[] -> edit[] 변환 (요구사항 3개)
    1) 수정 위치
    2) 수정할 글
    3) 수정 이유
    """
    edits: List[Dict[str, Any]] = []

    for i in issues:
        if not isinstance(i, dict):
            continue

        loc = i.get("location") if isinstance(i.get("location"), dict) else {}
        hint = i.get("evidence") or i.get("title") or loc.get("hint") or ""

        location = {
            "chunk_idx": loc.get("chunk_idx"),
            "hint": hint,
        }

        rewrite = i.get("rewrite") or i.get("suggestion") or "수정 문장을 제안하지 못했습니다."
        reason = i.get("reason") or i.get("message") or "설정/전개와의 충돌 가능성이 있습니다."

        edits.append({"location": location, "rewrite": rewrite, "reason": reason})

    return edits


def finalize_episode(
    episode_no: int,
    episode_facts: Dict[str, Any],
    issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    지금 단계에서는 '리포트 생성' 정도만.
    (원하면 이후에 story_state 업데이트까지 붙이면 됨)
    """
    return {
        "episode_no": episode_no,
        "issue_count": len(issues),
        "edits": issues_to_edits(issues),
    }
