from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.characters import Base, engine, get_db
from app.common.characters import CharacterCreate, CharacterUpdate, CharacterOut
from app.common import crud

app = FastAPI(
    title="Moneta Common Tool API",
    description="팀 공용 캐릭터 데이터베이스 (관계 포함 JSON 저장)",
)

# 최초 실행 시 테이블 생성
Base.metadata.create_all(bind=engine)

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
