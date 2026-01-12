from pydantic import BaseModel, Field


class IngestRawRequest(BaseModel):
    episode_no: int = Field(..., ge=1)
    raw_text: str = Field(..., min_length=1)
