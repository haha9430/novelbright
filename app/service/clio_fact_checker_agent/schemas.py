from pydantic import BaseModel
from typing import List, Optional

class IngestRequest(BaseModel):
    text: str

class RelatedEntitySchema(BaseModel):
    relation_type: str
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    description: Optional[str] = None

class HistoryCreate(BaseModel):
    name: str
    entity_type: str = "Unknown"
    era: Optional[str] = ""
    summary: Optional[str] = ""
    description: Optional[str] = ""
    tags: List[str] = []
    related_entities: List[RelatedEntitySchema] = []

class HistoryUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    era: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    related_entities: Optional[List[RelatedEntitySchema]] = None

class HistoryOut(BaseModel):
    id: str
    name: str
    entity_type: str
    era: str
    summary: str
    description: str
    tags: List[str]
    related_entities: List[RelatedEntitySchema]
    created_at: str
    updated_at: str

class ManuscriptInput(BaseModel):
    title: str
    content: str

class HistoryUpsertRequest(BaseModel):
    id: str             # 프론트에서 생성한 UUID
    title: str          # 제목
    content: str        # 내용