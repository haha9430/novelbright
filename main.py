# main.py (프로젝트 루트 위치)
from dotenv import load_dotenv
load_dotenv()  # .env 파일을 읽어서 환경변수로 로드함

from fastapi import FastAPI
from contextlib import asynccontextmanager

# [Import 경로 수정] app 패키지 내부 깊숙한 곳에 있는 라우터들을 가져옵니다.
from app.service.clio_fact_checker_agent.router import router as manuscript_router
from app.service.clio_fact_checker_agent.history_router import router as history_router
from app.service.story_keeper_agent.api import router as story_keeper_router

# 공용 모듈 Import
from app.common.history import repo as history_repo
from app.common.history.vector_store import vector_store
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import uuid

# DB 파일 경로 (루트 기준이므로 app/... 으로 시작)
HISTORY_DB_PATH = "app/data/history_db.json"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [Startup] 서버 시작: History DB 점검 중...")

    # 1. DB 파일 초기화 확인
    history_repo.init_db(HISTORY_DB_PATH)

    # 2. 벡터 스토어 동기화 (기존 데이터 로드)
    current_entities = history_repo.list_entities(HISTORY_DB_PATH)
    vector_store.sync_from_json(current_entities)

    yield
    print("👋 [Shutdown] 서버 종료")

app = FastAPI(
    title="Moneta Project Server",
    description="Fact Checker & History DB API",
    lifespan=lifespan
)

# CORS 설정 (Streamlit과의 통신 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# [Models] 데이터 모델
# --------------------------------------------------------------------------

class DocumentPayload(BaseModel):
    doc_id: str
    title: str = ""
    content: str

class MaterialPayload(BaseModel):
    id: str
    title: str
    category: str
    content: str
# --------------------------------------------------------------------------
# [API] 문서 (Documents)
# --------------------------------------------------------------------------

@app.post("/documents/save", tags=["Document"])
def api_save_document(doc: DocumentPayload):
    print(f"📥 [Doc Save] {doc.title} (ID: {doc.doc_id}) - {len(doc.content)}자")
    return {"status": "success", "msg": "문서가 저장되었습니다."}


# --------------------------------------------------------------------------
# [API] 분석 (Moneta AI)
# --------------------------------------------------------------------------

@app.post("/analyze/text", tags=["Analysis"])
def api_analyze_text(payload: DocumentPayload):
    content = payload.content
    print(f"🔄 [Analyze] 요청: {len(content)}자")

    # 더미 분석 로직 (키워드에 따라 다른 반응)
    results = []

    # 1. 역사 고증 (Clio)
    if "1820" in content or "나폴레옹" in content:
        results.append({
            "role": "clio",
            "msg": "나폴레옹은 1821년에 사망했습니다. 1820년에는 세인트헬레나 섬에 유배 중이었습니다.",
            "fix": "연도 확인 필요"
        })
    else:
        results.append({
            "role": "clio",
            "msg": "역사적 배경 검토 완료 (특이사항 없음)",
            "fix": "-"
        })

    # 2. 설정 오류 (Story Keeper)
    if "대검" in content and "사격" in content:
        results.append({
            "role": "story",
            "msg": "주인공은 '대검' 사용자인데 '사격'을 하고 있습니다.",
            "fix": "무기 설정 충돌"
        })
    else:
        results.append({
            "role": "story",
            "msg": "설정 충돌 없음",
            "fix": "-"
        })

    return results


# --------------------------------------------------------------------------
# [API] 자료실 (Materials)
# --------------------------------------------------------------------------

@app.post("/materials/save", tags=["Materials"])
def api_save_material(mat: MaterialPayload):
    print(f"📚 [Mat Save] {mat.title} ({mat.category})")
    return {"status": "success", "msg": f"자료 '{mat.title}' 저장 완료"}


@app.delete("/materials/{material_id}", tags=["Materials"])
def api_delete_material(material_id: str):
    print(f"🗑️ [Mat Delete] ID: {material_id}")
    return {"status": "success", "msg": "자료 삭제 완료"}

# ---------------------------------------------------------
# 라우터 등록 (Include Routers)
# ---------------------------------------------------------
# 1. 원고 분석 API (/manuscript)
app.include_router(manuscript_router)

# 2. 역사 DB 관리 API (/history)
app.include_router(history_router)

app.include_router(story_keeper_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}

# 실행 명령: uvicorn main:app --reload