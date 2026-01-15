import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any

# [추가] Solar 임베딩을 사용하기 위한 라이브러리 임포트
from langchain_upstage import UpstageEmbeddings

#HROMA_DB_PATH = os.path.join(os.getcwd(), "app/data/chroma_db")
COLLECTION_NAME = "history_collection"

# [수정] 전역 클라이언트 (재연결 방지)
_shared_client = None

class ManuscriptRepository:
    def __init__(self):
        global _shared_client

        # [추가] DB 저장 때 사용했던 것과 동일한 임베딩 함수 생성
        # (API KEY는 환경변수에 있거나 직접 넣어야 함)
        self.embedding_function = UpstageEmbeddings(model="solar-embedding-1-large")

        if _shared_client is None:
            print(f"📂 [ManuscriptRepo] 로컬 DB 경로 연결: {CHROMA_DB_PATH}")
            _shared_client = chromadb.HttpClient(
                host=chroma_host,
                port=int(chroma_port),
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )

        self.client = _shared_client

        # 컬렉션 가져오기
        try:
            self.collection = self.client.get_collection(name=COLLECTION_NAME)
        except Exception:
            # 혹시 컬렉션이 아직 안 만들어졌을 경우를 대비 (보통 vector_store에서 만들지만 안전하게)
            print(f"⚠️ 컬렉션 '{COLLECTION_NAME}'을 찾을 수 없습니다. (아직 데이터가 없을 수 있음)")
            self.collection = None

    def search(self, query_text: str, n_results: int = 1) -> Dict[str, Any]:
        if self.collection is None:
            print("⚠️ 컬렉션이 없어서 검색을 수행할 수 없습니다.")
            return {"documents": [[]], "distances": [[]]}

        try:
            # 텍스트를 벡터로 변환 (Solar 임베딩)
            query_vector = self.embedding_function.embed_query(query_text)

            # 쿼리 수행
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"⚠️ 검색 중 오류 발생: {e}")
            return {"documents": [[]], "distances": [[]]}