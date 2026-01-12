from pydantic import BaseModel, Field
from typing import List

class IngestEpisodeRequest(BaseModel):
    episode_no: int = Field(..., ge=1)
    text_chunks: List[str] = Field(..., min_items=1)

class IngestEpisodeResponse(BaseModel):
    episode_no: int
    full_text: str
