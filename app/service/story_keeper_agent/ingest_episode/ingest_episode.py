from typing import List, Optional
from pydantic import ValidationError

from .schemas import IngestEpisodeRequest, IngestEpisodeResponse


class IngestEpisodeError(ValueError):
    pass


def ingest_episode(
    req: Optional[IngestEpisodeRequest] = None,
    *,
    episode_no: Optional[int] = None,
    text_chunks: Optional[List[str]] = None,
) -> IngestEpisodeResponse:
    """
    내부 유틸: 두 가지 호출을 모두 지원
    1) ingest_episode(req=IngestEpisodeRequest(...))
    2) ingest_episode(episode_no=..., text_chunks=[...])

    => API에서 어떤 형태로 호출해
도 서버가 500으로 터지지 않게 방어
    """
    if req is None:
        try:
            req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=text_chunks)  # type: ignore
        except ValidationError as e:
            raise IngestEpisodeError(str(e))

    chunks = req.text_chunks

    if not isinstance(chunks, list) or len(chunks) == 0:
        raise IngestEpisodeError("text_chunks는 비어있을 수 없습니다.")

    cleaned: List[str] = []
    for i, ch in enumerate(chunks):
        if not isinstance(ch, str):
            raise IngestEpisodeError(f"chunk[{i}]는 문자열이어야 합니다.")

        s = ch.strip()
        if not s:
            raise IngestEpisodeError(f"chunk[{i}]가 비어 있습니다(공백만 존재).")

        if len(s) > 2500:
            raise IngestEpisodeError(f"chunk[{i}] 길이가 2500자를 초과했습니다: {len(s)}")

        cleaned.append(s)

    full_text = "\n".join(cleaned).strip()

    # ✅ 여기서 요약+저장 (return 이전, episode_no는 req.episode_no 사용)
    try:
        from app.service.story_keeper_agent.load_state.extracter import PlotManager

        manager = PlotManager()
        save_res = manager.summarize_and_save(episode_no=req.episode_no, full_text=full_text)

        if save_res.get("status") != "success":
            raise IngestEpisodeError(f"story_history 저장 실패: {save_res}")

    except IngestEpisodeError:
        raise
    except Exception as e:
        # FastAPI에서 500 방지용으로 에러를 명확히 래핑
        raise IngestEpisodeError(f"story_history 저장 중 예외: {repr(e)}")

    return IngestEpisodeResponse(
        episode_no=req.episode_no,
        full_text=full_text,
    )
