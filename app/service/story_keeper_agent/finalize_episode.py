from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.service.story_keeper_agent.rules.check_consistency import TYPE_LABELS


_WS_RE = re.compile(r"\s+")
_BAD_REASON_PREFIX = re.compile(
    r"^(?:.*?)(?:설정에\s*따라|설정상|명시되어|~~를\s*따라|world_rules|plot_rules|character_rules|history).*?(?:입니다\.?|됨\.?|사유.*?입니다\.?)\s*",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").strip())


def _clean_reason(reason: str) -> str:
    r = (reason or "").strip()
    if not r:
        return r
    # 너무 공격적으로 지우면 내용도 날아가니까, "앞부분"만 살짝 정리
    r2 = _BAD_REASON_PREFIX.sub("", r).strip()
    return r2 if r2 else r


def _best_line_match(lines: List[str], target: str) -> Optional[int]:
    """
    target(LLM sentence)이 원문과 완전일치 안 해도
    가장 비슷한 line index(1-based)를 찾아준다.
    """
    t = _norm(target)
    if not t:
        return None

    # 너무 짧으면(예: 3~4글자) 오탐이 심해서 컷
    if len(t) < 8:
        return None

    best_i = None
    best_score = 0.0

    # target의 앞부분을 키로 쓰면 잡히는 확률이 높음
    key = t[:60]

    for i, line in enumerate(lines, start=1):
        ln = _norm(line)
        if not ln:
            continue

        # 빠른 필터: key 일부가 포함되면 가산
        bonus = 0.08 if key and (key[:20] in ln) else 0.0

        # 유사도
        score = SequenceMatcher(None, t, ln).ratio() + bonus

        if score > best_score:
            best_score = score
            best_i = i

    # 임계값: 너무 낮으면 줄 찾기 실패 처리
    if best_i is None or best_score < 0.55:
        return None
    return best_i


def _find_line_span(raw_text: str, sentence: str) -> Optional[Tuple[int, int]]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    if not isinstance(sentence, str) or not sentence.strip():
        return None

    text = raw_text
    sent = sentence.strip()

    # 1) 완전일치 먼저
    idx = text.find(sent)
    if idx != -1:
        start_line = text.count("\n", 0, idx) + 1
        end_pos = idx + len(sent)
        end_line = text.count("\n", 0, end_pos) + 1
        return (start_line, end_line)

    # 2) 라인 단위 fuzzy
    lines = text.splitlines()
    best = _best_line_match(lines, sent)
    if best is None:
        return None
    return (best, best)


def issues_to_edits(
    issues: List[Dict[str, Any]],
    *,
    episode_no: int,
    raw_text: str,
) -> List[Dict[str, Any]]:
    edits: List[Dict[str, Any]] = []
    if not isinstance(issues, list):
        return edits

    for it in issues:
        if not isinstance(it, dict):
            continue

        issue_type = str(it.get("type", "") or "").strip().lower()
        type_label = TYPE_LABELS.get(issue_type, "기타 오류")

        title = str(it.get("title") or "").strip()

        sentence = it.get("sentence")
        sentence = sentence.strip() if isinstance(sentence, str) else None

        reason = _clean_reason(str(it.get("reason") or ""))
        rewrite = str(it.get("rewrite") or "").strip()

        location = None
        if sentence:
            span = _find_line_span(raw_text, sentence)
            if span:
                s, e = span
                location = f"{episode_no}화-{s}줄" if s == e else f"{episode_no}화-{s}~{e}줄"
            else:
                location = f"{episode_no}화-줄찾기실패"

        edits.append({
            "type_label": type_label,
            "title": title,
            "location": location,
            "sentence": sentence,
            "reason": reason,
            "rewrite": rewrite,
        })

    return edits
