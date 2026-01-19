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

    if req is None:
        try:
            req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=text_chunks)
        except ValidationError as e:
            raise IngestEpisodeError(str(e))

    chunks = req.text_chunks
    full_text = "\n".join(chunks).strip()

    try:
        from app.service.story_keeper_agent.load_state.extracter import PlotManager
        manager = PlotManager()
        res = manager.summarize_and_save(req.episode_no, full_text)
        if res.get("status") != "success":
            raise IngestEpisodeError("story_history 저장 실패")
    except Exception as e:
        raise IngestEpisodeError(str(e))

    return IngestEpisodeResponse(
        episode_no=req.episode_no,
        full_text=full_text,
    )
