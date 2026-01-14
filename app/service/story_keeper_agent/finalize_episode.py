from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.service.story_keeper_agent.rules.check_consistency import TYPE_LABELS

_WS_RE = re.compile(r"\s+")

# ✅ reason 앞에 붙는 '설정/앵커/anchors' 같은 시스템 설명을 제거
_BAD_REASON_PREFIX = re.compile(
    r"^(?:.*?)(?:설정에\s*따라|설정상|명시되어|world_rules|plot_rules|character_rules|history).*?(?:입니다\.?|됨\.?)\s*",
    re.IGNORECASE,
)

# ✅ anchors/앵커/anchor로 시작하는 이유문은 앞 덩어리를 잘라냄 (첫 구분자까지)
_ANCHORISH_START = re.compile(r"^\s*(?:anchors?|앵커|anchor)\b", re.IGNORECASE)

# ✅ '…으나/…지만/…인데/…으로' 같은 접속/전환 표현을 기준으로 앞을 잘라내기
_CLAUSE_CUT = re.compile(
    r"^.*?(?:,\s*|\.?\s+)(?=(?:원고|본문|해당|그래서|따라서|즉|결과적으로))",
    re.IGNORECASE,
)
# 콤마/마침표 없이도 자주 나오는 패턴: "…으나/…지만/…인데/…으로"
_CONJ_CUT = re.compile(r"^.*?(?:으나|지만|는데|인데|반면|그러나)\s*")


def _norm(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").strip())


def _clean_reason(reason: str) -> str:
    r = (reason or "").strip()
    if not r:
        return r

    # 1) 기존 제거(설정상/명시되어 등)
    r2 = _BAD_REASON_PREFIX.sub("", r).strip()
    if r2:
        r = r2

    # 2) ✅ anchors/앵커로 시작하면 "anchors에서는~" 같은 앞부분 제거
    if _ANCHORISH_START.match(r):
        # (a) "…, 그래서/원고에서/..." 처럼 다음 문장으로 넘어가는 경우
        cut = _CLAUSE_CUT.sub("", r).strip()
        if cut and cut != r:
            r = cut
        else:
            # (b) "…으나/…지만/…인데" 같은 전환 접속어 기준
            cut2 = _CONJ_CUT.sub("", r).strip()
            if cut2 and cut2 != r:
                r = cut2

        # (c) 그래도 "anchors"가 남아있으면 맨 앞 토큰만 강제로 제거
        r = re.sub(r"^\s*(?:anchors?|앵커|anchor)\s*(?:에서|에서는|기준으로|기준상)?\s*", "", r, flags=re.IGNORECASE).strip()

    return r


def _best_line_match(lines: List[str], target: str) -> Optional[int]:
    t = _norm(target)
    if not t or len(t) < 2:
        return None

    best_i = None
    best_score = 0.0
    key = t[:60]

    for i, line in enumerate(lines, start=1):
        ln = _norm(line)
        if not ln:
            continue

        if t in ln:
            return i

        bonus = 0.08 if key and (key[:20] in ln) else 0.0
        score = SequenceMatcher(None, t, ln).ratio() + bonus

        if score > best_score:
            best_score = score
            best_i = i

    if best_i is None or best_score < 0.4:
        return None
    return best_i


def _find_line_span(lines: List[str], raw_text: str, sentence: str) -> Optional[Tuple[int, int]]:
    if not sentence or not sentence.strip():
        return None

    idx = raw_text.find(sentence)
    if idx != -1:
        start_line = raw_text.count("\n", 0, idx) + 1
        end_pos = idx + len(sentence)
        end_line = raw_text.count("\n", 0, end_pos) + 1
        return (start_line, end_line)

    best = _best_line_match(lines, sentence)
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

    lines = raw_text.splitlines()

    for it in issues:
        if not isinstance(it, dict):
            continue

        issue_type = str(it.get("type", "") or "").strip().lower()
        type_label = TYPE_LABELS.get(issue_type, "기타 오류")
        title = str(it.get("title") or "").strip()

        sentence = it.get("sentence")
        sentence = sentence.strip() if isinstance(sentence, str) else ""

        # ✅ 여기서 reason을 사람 말처럼 정리
        reason = _clean_reason(str(it.get("reason") or ""))

        rewrite = str(it.get("rewrite") or "").strip()
        severity = str(it.get("severity") or "medium").lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"

        location = ""
        if sentence:
            span = _find_line_span(lines, raw_text, sentence)
            if span:
                s, e = span
                location = f"{episode_no}화-{s}줄" if s == e else f"{episode_no}화-{s}~{e}줄"

        edits.append(
            {
                "type_label": type_label,
                "title": title,
                "location": location,
                "sentence": sentence,
                "reason": reason,
                "rewrite": rewrite,
                "severity": severity,
            }
        )

    return edits


def finalize_episode(episode_no: int, facts: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw_text = facts.get("raw_text", "") if isinstance(facts, dict) else ""
    edits = issues_to_edits(issues=issues, episode_no=int(episode_no), raw_text=raw_text)
    return {"edits": edits}
