import sys
import os

sys.path.insert(0, os.getcwd())

from fastapi import FastAPI, APIRouter, HTTPException, Body
from pydantic import ValidationError
import uvicorn

# ✅ [수정] IngestEpisodeRequest(상자)를 추가로 가져옵니다.
from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeError,
    IngestEpisodeRequest
)
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state import load_state
from app.service.story_keeper_agent.load_state.extracter import PlotManager

app = FastAPI()
router = APIRouter(prefix="/story", tags=["story-keeper"])
manager = PlotManager()


def _extract_text_from_response(res):
    if isinstance(res, dict):
        return res.get("full_text") or res.get("content") or res.get("text") or res.get("body") or ""
    if hasattr(res, "full_text"): return res.full_text
    if hasattr(res, "content"): return res.content
    if hasattr(res, "text"): return res.text
    if hasattr(res, "body"): return res.body
    return str(res)


def _safe_load_state(episode_no: int) -> dict:
    try:
        return load_state(episode_no)
    except Exception as e:
        return {"status": "error", "message": f"load_state 실패: {repr(e)}", "data": {}}


def _light_response(res, chunks, raw_text, story_state, analysis_result):
    full_text = _extract_text_from_response(res)
    ep_no = getattr(res, "episode_no", None)
    return {
        "episode_no": ep_no,
        "full_text_len": len(full_text),
        "chunk_count": len(chunks),
        "preview": full_text[:200] if full_text else "",
        "story_state": story_state,
        "analysis": analysis_result,
    }


@router.post("/setting")
def update_setting(text: str = Body(..., media_type="text/plain")):
    return manager.update_global_settings(text)


@router.post("/ingest_plain")
def ingest_plain(
        episode_no: int,
        raw_text: str = Body(..., media_type="text/plain"),
):
    try:
        # 1. 청크 자르기
        chunks = split_into_chunks(raw_text, max_len=2500, min_len=1500)

        # 2. [수정] 상자(Request)에 담기
        # ⚠️ 만약 여기서 에러가 나면 'chunks' 라는 이름이 틀린 겁니다. (schemas.py 확인 필요)
        try:
            req = IngestEpisodeRequest(episode_no=episode_no, chunks=chunks)
        except ValidationError:
            # 혹시 이름이 text_chunks일 수도 있어서 예비로 시도
            req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks)

        # 3. 친구분 코드에 상자째로 전달
        res = ingest_episode(req)

        full_text_str = _extract_text_from_response(res)
        analysis_response = manager.summarize_and_save(episode_no, full_text_str)
        story_state = _safe_load_state(episode_no)

        return _light_response(res, chunks, raw_text, story_state, analysis_response.get("data"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)