from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

#from app.common.characters import Base, engine, get_db
#from app.common.characters import CharacterCreate, CharacterUpdate, CharacterOut
#from app.common import crud

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.common.history import repo as history_repo
from app.common.history.vector_store import vector_store
from app.service.history.solar_client import HistoryLLMClient
from app.service.history.ingest_history import normalize_payload
#from app.deps import get_manuscript_analyzer
from app.service.manuscript.analyzer import ManuscriptAnalyzer

app = FastAPI(
    title="Moneta Common Tool API",
    description="팀 공용 캐릭터 데이터베이스 (관계 포함 JSON 저장)",
)

@app.on_event("startup")
async def startup_event():
    print("🚀 서버 시작: History 벡터 DB 인덱싱 점검...")
    # JSON 파일을 읽어서 벡터 DB를 최신 상태로 만듦
    current_entities = history_repo.list_entities(HISTORY_DB_PATH)
    vector_store.sync_from_json(current_entities)

# 최초 실행 시 테이블 생성
#Base.metadata.create_all(bind=engine)

# History (JSON) 파일 경로 상수
HISTORY_DB_PATH = "app/common/data/history_db.json"
PLOT_DB_PATH = "app/common/data/plot.json"

# 서버 시작 시 History DB 파일이 없으면 생성
history_repo.init_db(HISTORY_DB_PATH)

# ---------------------------------------------------------
# History용 Pydantic 모델 정의 (DTO)
# ---------------------------------------------------------
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

@app.get("/health")
def health():
    return {"status": "ok", "tool": "common"}
'''
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
'''
# ---------------------------------------------------------
# History Helper Function
# ---------------------------------------------------------
def _normalize_ingest_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """LLM이 준 데이터를 DB 스키마에 맞게 깔끔하게 정리합니다."""
    return {
        "name": str(raw_payload.get("name", "")).strip(),
        "entity_type": str(raw_payload.get("entity_type", "Unknown")).strip(),
        "era": str(raw_payload.get("era", "")).strip(),
        "summary": str(raw_payload.get("summary", "")).strip(),
        "description": str(raw_payload.get("description", "")).strip(),
        # 리스트가 None일 경우 빈 리스트로 방어
        "tags": [str(t).strip() for t in raw_payload.get("tags", []) or []],
        "related_entities": raw_payload.get("related_entities", []) or []
    }

def _merge_entity_data(existing: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    기존 데이터(existing)에 새로운 데이터(new_data)를 덧입힙니다.
    - 텍스트 필드: 새로운 값이 비어있지 않으면 덮어씌움 (최신 정보 반영)
    - 리스트 필드(tags, related): 기존 값과 합침 (중복 제거)
    """
    merged = existing.copy()

    # 1. 텍스트 필드 업데이트 (새 데이터가 있을 때만)
    for key in ["name", "entity_type", "era", "summary", "description"]:
        if new_data.get(key):
            merged[key] = new_data[key]

    # 2. 태그 병합 (중복 제거)
    old_tags = set(existing.get("tags", []))
    new_tags = set(new_data.get("tags", []))
    merged["tags"] = list(old_tags | new_tags) # 합집합

    # 3. 관계 데이터 병합 (단순 병합보다는, 대상 이름 기준으로 중복 방지)
    # 기존 관계 맵핑 (target_name -> relation 객체)
    existing_rels = {r["target_name"]: r for r in existing.get("related_entities", [])}

    for new_rel in new_data.get("related_entities", []):
        t_name = new_rel.get("target_name")
        # 새로운 관계거나, 설명이 더 길면 업데이트한다고 가정
        if t_name:
            existing_rels[t_name] = new_rel

    merged["related_entities"] = list(existing_rels.values())

    return merged

# ---------------------------------------------------------
# History API (JSON Repo)
# ---------------------------------------------------------
@app.get("/history", response_model=List[HistoryOut], tags=["History"])
def api_list_history_entities():
    """전체 역사 엔티티 목록 조회"""
    return history_repo.list_entities(HISTORY_DB_PATH)

@app.get("/history/search", response_model=List[HistoryOut], tags=["History"])
def api_search_history(q: str = Query(..., description="검색할 키워드")):
    """
        이제 키워드 검색 시 벡터 DB를 사용합니다!
    """
    # 1. 벡터 검색 수행
    results = vector_store.search(q, top_k=5)

    # 2. 결과 매핑 (Document -> HistoryOut)
    response_list = []
    for doc, score in results:
        # 벡터 DB에는 요약된 텍스트만 있으므로,
        # 필요하다면 ID를 가지고 repo.get_entity()로 원본 상세 데이터를 다시 가져와도 됩니다.
        # 여기서는 메타데이터를 활용해 반환합니다.
        entity_id = doc.metadata["id"]

        # 원본 데이터 조회 (가장 확실한 방법)
        original_data = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
        if original_data:
            response_list.append(original_data)

    return response_list

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

@app.post("/history/ingest", tags=["History"])
def api_ingest_history_text(payload: IngestRequest):
    """
    텍스트를 분석하여 DB에 반영합니다. (Upsert: 이미 있으면 수정, 없으면 생성)
    배치 처리를 위해 벡터 DB 동기화는 맨 마지막에 한 번만 수행합니다.
    """
    input_text = payload.text
    print(f"🔄 [API] 텍스트 분석 및 병합 시도 ({len(input_text)}자)...")

    client = HistoryLLMClient()
    try:
        commands = client.parse_history_command(input_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

    if not commands:
        return {"summary": "처리된 항목 없음", "details": []}

    results = []
    success_count = 0

    # 1. 반복문 시작
    for cmd in commands:
        suggested_action = cmd.get("action", "create")
        target_name = cmd.get("target", {}).get("name")

        # DB에서 동명이인 검색
        existing_id = history_repo.find_id_by_name(HISTORY_DB_PATH, target_name)

        final_action = suggested_action
        final_target_id = existing_id

        # Upsert 로직: create인데 이미 있으면 update로 변경
        if suggested_action == "create" and existing_id:
            final_action = "update"
            print(f"ℹ️ 중복 발견: '{target_name}'(ID:{existing_id}) -> 'Create'를 'Update'로 전환합니다.")

        log_item = {"name": target_name, "action": final_action, "status": "pending"}

        try:
            raw_payload = cmd.get("payload", {})
            normalized_payload = _normalize_ingest_payload(raw_payload)

            if final_action == "create":
                # [중요] auto_sync=False로 설정하여 매번 동기화 방지
                saved_entity = history_repo.create_entity(HISTORY_DB_PATH, normalized_payload, auto_sync=False)

                log_item.update({
                    "status": "success",
                    "id": saved_entity["id"],
                    "message": "새로 생성됨",
                    "result_data": saved_entity
                })
                success_count += 1

            elif final_action == "update":
                if not final_target_id:
                    raise ValueError(f"수정할 대상 ID를 찾지 못함: {target_name}")

                # 기존 데이터 조회
                existing_entity = history_repo.get_entity(HISTORY_DB_PATH, final_target_id)
                if not existing_entity:
                    raise ValueError("ID는 찾았으나 실제 데이터가 없습니다.")

                # [수정됨] 병합(Merge)을 먼저 수행해야 함!
                merged_data = _merge_entity_data(existing_entity, normalized_payload)

                # 업데이트 수행 (auto_sync=False)
                updated_entity = history_repo.update_entity(HISTORY_DB_PATH, final_target_id, merged_data, auto_sync=False)

                log_item.update({
                    "status": "success",
                    "id": updated_entity["id"],
                    "message": "기존 정보에 병합됨",
                    "result_data": updated_entity
                })
                success_count += 1

            elif final_action == "delete":
                if final_target_id:
                    history_repo.delete_entity(HISTORY_DB_PATH, final_target_id, auto_sync=False)
                    log_item.update({"status": "success", "id": final_target_id, "message": "삭제됨"})
                    success_count += 1
                else:
                    raise ValueError(f"삭제할 대상을 찾을 수 없음: {target_name}")

        except Exception as e:
            log_item.update({"status": "error", "message": str(e)})
            print(f"⚠️ 처리 실패 ({target_name}): {e}")

        # [중요] 처리 결과 기록은 반복문 안에서!
        results.append(log_item)

    # 2. 반복문 종료 후 일괄 동기화 (들여쓰기 주의!)
    if success_count > 0:
        print("🔄 [API] 일괄 변경 완료. 벡터 DB 동기화를 수행합니다...")
        try:
            history_repo.force_sync_vector_db(HISTORY_DB_PATH)
        except Exception as e:
            print(f"⚠️ 벡터 DB 동기화 중 오류 발생: {e}")

    # 3. 최종 반환 (들여쓰기 주의!)
    return {
        "summary": f"총 {len(commands)}건 중 {success_count}건 처리 완료",
        "details": results
    }

'''
@app.post("/manuscript/analyze", tags=["Manuscript"])
def api_analyze_manuscript(
        payload: ManuscriptInput,
        # 👇 의존성 주입: deps.py가 Analyzer를 조립해서 가져다줍니다.
        analyzer: ManuscriptAnalyzer = Depends(get_manuscript_analyzer)
):
    """
    원고(5000자 이상 가능)를 입력받아 설정 DB(plot.json)와 역사 DB를 교차 검증합니다.
    1. 긴 텍스트를 문맥 단위로 분할(Chunking)
    2. 각 청크에서 주요 키워드 추출
    3. 설정에 없는 키워드만 역사 DB에서 조회
    """
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="내용이 비어있습니다.")

    try:
        # Analyzer 서비스 호출
        result = analyzer.analyze_manuscript(payload.content)

        return {
            "title": payload.title,
            "analysis_result": result
        }
    except Exception as e:
        print(f"❌ 원고 분석 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
'''
@app.post("/manuscript/analyze", tags=["Manuscript"])
async def api_analyze_manuscript(
        title: str = Form(...),          # Form 데이터로 받음
        file: UploadFile = File(...)     # 파일 객체로 받음
):
    """
    파일 업로드 방식의 원고 분석 API
    """
    try:
        # 1. 파일 내용 읽기 (bytes -> str 디코딩)
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8") # 인코딩에 따라 cp949 일 수도 있음

        # 2. 분석기 생성 (임시 Repo 사용)
        analyzer = ManuscriptAnalyzer(setting_path=PLOT_DB_PATH)

        # 3. 분석 수행
        result = analyzer.analyze_manuscript(content)

        return {
            "title": title,
            "filename": file.filename,
            "analysis_result": result
        }
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩 형식이 맞지 않습니다 (UTF-8 권장)")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))