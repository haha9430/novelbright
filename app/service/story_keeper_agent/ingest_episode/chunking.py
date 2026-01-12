import re
from typing import List


_END_PUNCTS = {".", "?", "!", "…"}
_KO_ENDINGS = ("다", "요", "죠", "네", "까")


def _split_sentences(text: str) -> List[str]:
    """
    정규식 split 대신, 순차 스캔으로 문장 분리.
    - ., ?, !, … 뒤에서 자름
    - 한국어 종결(다/요/죠/네/까) + (. 또는 ?) 패턴도 자름
    - 줄바꿈은 문장 경계로 취급 (여러 줄은 하나로 합치지 않음)
    """
    s = text.strip()
    if not s:
        return []

    out: List[str] = []
    buf: List[str] = []

    def flush():
        nonlocal buf
        chunk = "".join(buf).strip()
        if chunk:
            out.append(chunk)
        buf = []

    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        buf.append(ch)

        # 줄바꿈은 경계
        if ch == "\n":
            flush()
            i += 1
            continue

        # 기호 종결 처리
        if ch in _END_PUNCTS:
            # 바로 뒤 공백/줄바꿈이면 문장 끝으로 판단
            if i + 1 == n or s[i + 1].isspace():
                flush()
            i += 1
            continue

        i += 1

    flush()

    # 너무 짧은 조각들이 생기면(예: 따옴표만 분리) 앞뒤로 흡수
    normalized: List[str] = []
    for part in out:
        if normalized and len(part) <= 2:
            normalized[-1] = (normalized[-1] + part).strip()
        else:
            normalized.append(part)

    return normalized


def split_into_chunks(
    raw_text: str,
    max_len: int = 2500,
    min_len: int = 1500,
) -> List[str]:
    """
    raw_text를 로직으로 청킹한다 (AI 사용 X)

    정책:
    - 문단(빈 줄) 우선
    - 문단이 max_len 초과면 문장 단위로만 분해하여 묶기
    - 문장 중간 분할은 하지 않음
    - 마지막 청크는 min_len 미만이어도 허용
    """
    if not isinstance(raw_text, str):
        raise ValueError("raw_text는 문자열이어야 합니다.")
    text = raw_text.strip()
    if not text:
        raise ValueError("raw_text가 비어 있습니다.")

    # 문단(빈 줄) 기준 분리
    paragraphs = [p for p in re.split(r"\n\s*\n+", text) if p.strip()]

    chunks: List[str] = []
    buf = ""

    def flush_buf():
        nonlocal buf
        t = buf.strip()
        if t:
            chunks.append(t)
        buf = ""

    for para in paragraphs:
        p = para.strip()

        # 문단이 짧으면 버퍼에 합치기
        if len(p) <= max_len:
            candidate = (buf + "\n\n" + p).strip() if buf else p
            if len(candidate) <= max_len:
                buf = candidate
            else:
                flush_buf()
                buf = p
            continue

        # 문단이 너무 길면 문장 분해
        sentences = _split_sentences(p)

        # 문장 분해가 실패하면(거의 없음) 안전 예외
        if not sentences:
            raise ValueError(
                "문단이 너무 길고 문장 분리에 실패했습니다. 줄바꿈을 추가하거나 문장을 더 짧게 나눠주세요."
            )

        for sent in sentences:
            # 한 문장이 max_len 초과면 정책상 예외
            if len(sent) > max_len:
                raise ValueError(
                    f"한 문장이 {max_len}자를 초과합니다. 문장을 더 짧게 나눠주세요. (len={len(sent)})"
                )

            candidate = (buf + " " + sent).strip() if buf else sent
            if len(candidate) <= max_len:
                buf = candidate
            else:
                flush_buf()
                buf = sent

        flush_buf()

    flush_buf()

    # 너무 짧은 청크를 앞 청크에 합칠 수 있으면 합침(마지막 제외 권장)
    if len(chunks) >= 2:
        normalized: List[str] = []
        for c in chunks:
            if normalized and len(c) < min_len and len(normalized[-1]) + 2 + len(c) <= max_len:
                normalized[-1] = (normalized[-1] + "\n\n" + c).strip()
            else:
                normalized.append(c)
        chunks = normalized

    return chunks
