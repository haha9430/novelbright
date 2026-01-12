from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.common.characters import Base, engine, get_db
from app.common.characters import CharacterCreate, CharacterUpdate, CharacterOut
from app.common import crud

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.common.history import repo as history_repo

app = FastAPI(
    title="Moneta Common Tool API",
    description="팀 공용 캐릭터 데이터베이스 (관계 포함 JSON 저장)",
)

# 최초 실행 시 테이블 생성
Base.metadata.create_all(bind=engine)

# History (JSON) 파일 경로 상수
HISTORY_DB_PATH = "app/common/data/history_db.json"

# 서버 시작 시 History DB 파일이 없으면 생성
history_repo.init_db(HISTORY_DB_PATH)

# ---------------------------------------------------------
# History용 Pydantic 모델 정의 (DTO)
# ---------------------------------------------------------
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

@app.get("/health")
def health():
    return {"status": "ok", "tool": "common"}

@app.post("/characters", response_model=CharacterOut)
def api_create_character(payload: CharacterCreate, db: Session = Depends(get_db)):
    try:
        obj = crud.create_character(db, payload)
        return obj.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/characters", response_model=list[CharacterOut])
def api_list_characters(db: Session = Depends(get_db)):
    items = crud.list_characters(db)
    return [i.__dict__ for i in items]

@app.get("/characters/{char_id}", response_model=CharacterOut)
def api_get_character(char_id: str, db: Session = Depends(get_db)):
    obj = crud.get_character(db, char_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not Found")
    return obj.__dict__

@app.patch("/characters/{char_id}", response_model=CharacterOut)
def api_update_character(char_id: str, payload: CharacterUpdate, db: Session = Depends(get_db)):
    try:
        obj = crud.update_character(db, char_id, payload)
        return obj.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------
# History API (JSON Repo)
# ---------------------------------------------------------
@app.get("/history", response_model=List[HistoryOut], tags=["History"])
def api_list_history_entities():
    """전체 역사 엔티티 목록 조회"""
    return history_repo.list_entities(HISTORY_DB_PATH)

@app.get("/history/search", response_model=List[HistoryOut], tags=["History"])
def api_search_history(q: str = Query(..., description="검색할 키워드")):
    """키워드 검색 (이름, 태그, 요약 등)"""
    return history_repo.search_by_keyword(HISTORY_DB_PATH, q)

@app.post("/history", response_model=HistoryOut, tags=["History"])
def api_create_history_entity(payload: HistoryCreate):
    """새로운 역사 엔티티 생성"""
    try:
        # Pydantic 모델 -> Dict 변환 후 repo 전달
        return history_repo.create_entity(HISTORY_DB_PATH, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/history/{entity_id}", response_model=HistoryOut, tags=["History"])
def api_get_history_entity(entity_id: str):
    """ID로 상세 조회"""
    entity = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    return entity

@app.patch("/history/{entity_id}", response_model=HistoryOut, tags=["History"])
def api_update_history_entity(entity_id: str, payload: HistoryUpdate):
    """엔티티 수정 (부분 업데이트)"""
    try:
        # 값이 있는 필드만 추출 (exclude_unset=True)
        update_data = payload.model_dump(exclude_unset=True)
        return history_repo.update_entity(HISTORY_DB_PATH, entity_id, update_data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/history/{entity_id}", tags=["History"])
def api_delete_history_entity(entity_id: str):
    """엔티티 삭제"""
    success = history_repo.delete_entity(HISTORY_DB_PATH, entity_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    return {"status": "deleted", "id": entity_id}