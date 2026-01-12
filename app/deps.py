from fastapi.params import Depends

from app.repository.vector.user_repo import UserRepository
from app.repository.vector.vector_repo import VectorRepository, ChromaDBRepository

from app.service.user_service import UserService
from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService
from app.service.agent_service import AgentService

from app.service.manuscript.analyzer import ManuscriptAnalyzer # [추가]

# 파일 경로 상수 (또는 config에서 가져오기)
PLOT_DB_PATH = "app/common/data/plot.json"

def get_user_repository() -> UserRepository:
    return UserRepository()


def get_vector_repository() -> VectorRepository:
    return ChromaDBRepository()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_vector_service(
    vector_repo: VectorRepository = Depends(get_vector_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
) -> VectorService:
    return VectorService(vector_repository=vector_repo, embedding_service=embedding_service)


def get_user_service(user_repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repo=user_repo)


def get_agent_service(vector_service: VectorService = Depends(get_vector_service)) -> AgentService:
    return AgentService(vector_service=vector_service)

def get_manuscript_analyzer(
    vector_service: VectorService = Depends(get_vector_service)
) -> ManuscriptAnalyzer:
    """
    ManuscriptAnalyzer를 생성하여 반환합니다.
    필요한 VectorService는 FastAPI가 자동으로 get_vector_service를 통해 주입해줍니다.
    """
    return ManuscriptAnalyzer(setting_path=PLOT_DB_PATH, vector_service=vector_service)
