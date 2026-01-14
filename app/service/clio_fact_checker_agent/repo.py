import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any

# [추가] Solar 임베딩을 사용하기 위한 라이브러리 임포트
from langchain_upstage import UpstageEmbeddings

CHROMA_DB_PATH = os.path.join(os.getcwd(), "app/data/chroma_db")
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
            _shared_client = chromadb.PersistentClient(
                path=CHROMA_DB_PATH,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )

        self.client = _shared_client

        # [중요] 컬렉션을 가져올 때 embedding_function을 명시해야 함!
        # ChromaDB 기본 클라이언트는 래핑이 안 되어 있어서,
        # langchain_chroma가 아니라면 query 시에 embeddings를 직접 넣어주는 게 안전할 수 있습니다.
        # 하지만 일반적으로는 get_collection에 embedding_function을 넣으면 자동 처리됩니다.
        self.collection = self.client.get_collection(
            name=COLLECTION_NAME,
            # 주의: ChromaDB 네이티브 client는 LangChain 객체를 바로 못 받을 수 있음.
            # 이 경우 아래 search 메서드에서 수동으로 임베딩해야 함.
        )

    def search(self, query_text: str, n_results: int = 1) -> Dict[str, Any]:
        try:
            # [수정] 텍스트를 바로 넣지 말고, Solar로 임베딩(숫자 변환)해서 넣기
            query_vector = self.embedding_function.embed_query(query_text)

            # query_texts 대신 query_embeddings 사용
            results = self.collection.query(
                query_embeddings=[query_vector], # 384차원 대신 4096차원 벡터가 들어감
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"⚠️ 검색 중 오류 발생: {e}")
            return {"documents": [[]], "distances": [[]]}