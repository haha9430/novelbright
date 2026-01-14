from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import uuid

# [기존 모듈 import 유지]
from app.common.history import repo as history_repo
from app.common.history.vector_store import vector_store
from app.service.history.solar_client import HistoryLLMClient
from app.service.history.ingest_history import normalize_payload
from app.service.manuscript.analyzer import ManuscriptAnalyzer

app = FastAPI(
    title="Moneta Common Tool API",
    description="팀 공용 캐릭터 데이터베이스 및 분석 도구",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# [임시 데이터베이스] In-Memory
# --------------------------------------------------------------------------
db_documents = {}
db_materials = {}


# --------------------------------------------------------------------------
# [Models] 데이터 모델 (수정됨)
# --------------------------------------------------------------------------

class DocumentPayload(BaseModel):
    doc_id: str
    title: str = ""
    content: str


# [수정] category 필드 삭제됨
class MaterialPayload(BaseModel):
    id: str
    title: str
    content: str


# [추가] 모듈별 분석 요청을 위한 모델
class AnalysisRequest(BaseModel):
    doc_id: str
    content: str
    modules: Optional[List[str]] = ["storykeeper", "clio"]


# --------------------------------------------------------------------------
# [API] 문서 (Documents)
# --------------------------------------------------------------------------

@app.post("/documents/save", tags=["Document"])
def api_save_document(doc: DocumentPayload):
    print(f"📥 [Doc Save] {doc.title} (ID: {doc.doc_id}) - {len(doc.content)}자")
    # 메모리 DB에 저장
    db_documents[doc.doc_id] = {
        "title": doc.title,
        "content": doc.content
    }
    return {"status": "success", "msg": "문서가 저장되었습니다."}


@app.get("/documents/{doc_id}", tags=["Document"])
def api_get_document(doc_id: str):
    if doc_id not in db_documents:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return db_documents[doc_id]


# --------------------------------------------------------------------------
# [API] 분석 (Moneta AI - 수정됨)
# --------------------------------------------------------------------------

@app.post("/analyze/text", tags=["Analysis"])
def api_analyze_text(req: AnalysisRequest):
    content = req.content
    modules = req.modules or []
    print(f"🔄 [Analyze] 요청: {len(content)}자 (Modules: {modules})")

    results = []

    # 1. 클리오 (역사 고증) - 모듈에 포함된 경우에만 실행
    if "clio" in modules:
        if "1820" in content or "나폴레옹" in content:
            results.append({
                "role": "clio",  # 프론트엔드에서는 'story'로 매핑됨 (role 이름은 프론트와 맞춰야 함)
                # 여기서는 프론트엔드가 'story'를 역사로 인식하므로 role을 'story'로 보냄
                "role": "story",
                "msg": "나폴레옹은 1821년에 사망했습니다. 1820년에는 세인트헬레나 섬에 유배 중이었습니다.",
                "fix": "연도 확인 필요"
            })
        else:
            # 오류가 없을 때는 빈 리스트여도 됨 (프론트에서 '오류 없음' 처리)
            pass

    # 2. 스토리키퍼 (개연성/설정) - 모듈에 포함된 경우에만 실행
    if "storykeeper" in modules:
        if "대검" in content and "사격" in content:
            results.append({
                "role": "logic",
                "msg": "주인공은 '대검' 사용자인데 '사격'을 하고 있습니다.",
                "fix": "무기 설정 충돌"
            })
        if "연대장" in content and "소대장" in content:
            results.append({
                "role": "logic",
                "msg": "설정 충돌 의심: 동일 인물 호칭 혼용",
                "fix": "시점에 따른 호칭인지 확인 필요"
            })

    return results


# --------------------------------------------------------------------------
# [API] 자료실 (Materials - 수정됨)
# --------------------------------------------------------------------------

@app.post("/materials/save", tags=["Materials"])
def api_save_material(mat: MaterialPayload):
    # [수정] category 관련 내용 제거 및 DB 저장
    print(f"📚 [Mat Save] {mat.title}")
    db_materials[mat.id] = mat.dict()
    return {"status": "success", "msg": f"자료 '{mat.title}' 저장 완료"}


@app.delete("/materials/{material_id}", tags=["Materials"])
def api_delete_material(material_id: str):
    print(f"🗑️ [Mat Delete] ID: {material_id}")
    if material_id in db_materials:
        del db_materials[material_id]
        return {"status": "success", "msg": "자료 삭제 완료"}
    return {"status": "error", "msg": "자료가 없습니다."}


# ==========================================================================
# 👇 아래부터는 기존 History 및 Manuscript 관련 코드 (유지)
# ==========================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

# History (JSON) 파일 경로 상수
HISTORY_DB_PATH = "app/common/data/history_db.json"
PLOT_DB_PATH = "app/common/data/plot.json"


@app.on_event("startup")
async def startup_event():
    print("🚀 서버 시작: History 벡터 DB 인덱싱 점검...")
    # JSON 파일을 읽어서 벡터 DB를 최신 상태로 만듦
    # (파일이 없으면 init_db가 생성해줌)
    history_repo.init_db(HISTORY_DB_PATH)

    current_entities = history_repo.list_entities(HISTORY_DB_PATH)
    if current_entities:
        vector_store.sync_from_json(current_entities)


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
        "tags": [str(t).strip() for t in raw_payload.get("tags", []) or []],
        "related_entities": raw_payload.get("related_entities", []) or []
    }


def _merge_entity_data(existing: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    merged = existing.copy()
    for key in ["name", "entity_type", "era", "summary", "description"]:
        if new_data.get(key):
            merged[key] = new_data[key]

    old_tags = set(existing.get("tags", []))
    new_tags = set(new_data.get("tags", []))
    merged["tags"] = list(old_tags | new_tags)

    existing_rels = {r["target_name"]: r for r in existing.get("related_entities", [])}
    for new_rel in new_data.get("related_entities", []):
        t_name = new_rel.get("target_name")
        if t_name:
            existing_rels[t_name] = new_rel
    merged["related_entities"] = list(existing_rels.values())
    return merged


# ---------------------------------------------------------
# History API (JSON Repo)
# ---------------------------------------------------------
@app.get("/history", response_model=List[HistoryOut], tags=["History"])
def api_list_history_entities():
    return history_repo.list_entities(HISTORY_DB_PATH)


@app.get("/history/search", response_model=List[HistoryOut], tags=["History"])
def api_search_history(q: str = Query(..., description="검색할 키워드")):
    results = vector_store.search(q, top_k=5)
    response_list = []
    for doc, score in results:
        entity_id = doc.metadata["id"]
        original_data = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
        if original_data:
            response_list.append(original_data)
    return response_list


@app.post("/history", response_model=HistoryOut, tags=["History"])
def api_create_history_entity(payload: HistoryCreate):
    try:
        return history_repo.create_entity(HISTORY_DB_PATH, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/history/{entity_id}", response_model=HistoryOut, tags=["History"])
def api_get_history_entity(entity_id: str):
    entity = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    return entity


@app.patch("/history/{entity_id}", response_model=HistoryOut, tags=["History"])
def api_update_history_entity(entity_id: str, payload: HistoryUpdate):
    try:
        update_data = payload.model_dump(exclude_unset=True)
        return history_repo.update_entity(HISTORY_DB_PATH, entity_id, update_data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/history/{entity_id}", tags=["History"])
def api_delete_history_entity(entity_id: str):
    success = history_repo.delete_entity(HISTORY_DB_PATH, entity_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    return {"status": "deleted", "id": entity_id}


@app.post("/history/ingest", tags=["History"])
def api_ingest_history_text(payload: IngestRequest):
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

    for cmd in commands:
        suggested_action = cmd.get("action", "create")
        target_name = cmd.get("target", {}).get("name")
        existing_id = history_repo.find_id_by_name(HISTORY_DB_PATH, target_name)
        final_action = suggested_action
        final_target_id = existing_id

        if suggested_action == "create" and existing_id:
            final_action = "update"
            print(f"ℹ️ 중복 발견: '{target_name}'(ID:{existing_id}) -> 'Create'를 'Update'로 전환합니다.")

        log_item = {"name": target_name, "action": final_action, "status": "pending"}

        try:
            raw_payload = cmd.get("payload", {})
            normalized_payload = _normalize_ingest_payload(raw_payload)

            if final_action == "create":
                saved_entity = history_repo.create_entity(HISTORY_DB_PATH, normalized_payload, auto_sync=False)
                log_item.update(
                    {"status": "success", "id": saved_entity["id"], "message": "새로 생성됨", "result_data": saved_entity})
                success_count += 1

            elif final_action == "update":
                if not final_target_id:
                    raise ValueError(f"수정할 대상 ID를 찾지 못함: {target_name}")
                existing_entity = history_repo.get_entity(HISTORY_DB_PATH, final_target_id)
                if not existing_entity:
                    raise ValueError("ID는 찾았으나 실제 데이터가 없습니다.")
                merged_data = _merge_entity_data(existing_entity, normalized_payload)
                updated_entity = history_repo.update_entity(HISTORY_DB_PATH, final_target_id, merged_data,
                                                            auto_sync=False)
                log_item.update({"status": "success", "id": updated_entity["id"], "message": "기존 정보에 병합됨",
                                 "result_data": updated_entity})
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
        results.append(log_item)

    if success_count > 0:
        print("🔄 [API] 일괄 변경 완료. 벡터 DB 동기화를 수행합니다...")
        try:
            history_repo.force_sync_vector_db(HISTORY_DB_PATH)
        except Exception as e:
            print(f"⚠️ 벡터 DB 동기화 중 오류 발생: {e}")

    return {"summary": f"총 {len(commands)}건 중 {success_count}건 처리 완료", "details": results}


@app.post("/manuscript/analyze", tags=["Manuscript"])
async def api_analyze_manuscript(
        title: str = Form(...),
        file: UploadFile = File(...)
):
    try:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8")
        analyzer = ManuscriptAnalyzer(setting_path=PLOT_DB_PATH)
        result = analyzer.analyze_manuscript(content)
        return {"title": title, "filename": file.filename, "analysis_result": result}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩 형식이 맞지 않습니다 (UTF-8 권장)")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))