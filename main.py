# main.py (프로젝트 루트 위치)
from dotenv import load_dotenv
load_dotenv()  # .env 파일을 읽어서 환경변수로 로드함

from fastapi import FastAPI
from contextlib import asynccontextmanager

# [Import 경로 수정] app 패키지 내부 깊숙한 곳에 있는 라우터들을 가져옵니다.
from app.service.clio_fact_checker_agent.router import router as manuscript_router
from app.service.clio_fact_checker_agent.history_router import router as history_router

# 공용 모듈 Import
from app.common.history import repo as history_repo
from app.common.history.vector_store import vector_store

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

# ---------------------------------------------------------
# 라우터 등록 (Include Routers)
# ---------------------------------------------------------
# 1. 원고 분석 API (/manuscript)
app.include_router(manuscript_router)

# 2. 역사 DB 관리 API (/history)
app.include_router(history_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}

# 실행 명령: uvicorn main:app --reload