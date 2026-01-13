# app/common/history/vector_store.py
import os
import shutil
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from langchain_chroma import Chroma
from langchain_upstage import UpstageEmbeddings
from langchain_core.documents import Document

# 벡터 DB가 저장될 로컬 폴더 경로
PERSIST_DIRECTORY = "app/data/chroma_db"

class HistoryVectorStore:
    def __init__(self):
        # 1. 임베딩 모델 설정 (Upstage Solar)
        self.embedding_model = UpstageEmbeddings(model="solar-embedding-1-large")

        # 2. ChromaDB 로드 (디스크에 저장된 데이터가 있으면 불러옴)
        self.vector_db = Chroma(
            collection_name="history_collection",
            embedding_function=self.embedding_model,
            persist_directory=PERSIST_DIRECTORY
        )

    def sync_from_json(self, entities: List[Dict[str, Any]]):
        """
        JSON 데이터를 받아 벡터 DB를 '통째로' 갱신합니다.
        (데이터 양이 적을 때는 이 방식이 무결성 유지에 가장 확실합니다)
        """
        print(f"🔄 벡터 DB 동기화 시작... ({len(entities)}건)")

        # 1. 기존 DB 삭제 후 재생성 (Clean Slate Strategy)
        # 데이터 꼬임을 방지하기 위해 초기화
        if os.path.exists(PERSIST_DIRECTORY):
            self.vector_db.delete_collection()

            # 2. Document 객체 리스트 생성
        documents = []
        for item in entities:
            # [중요] 검색에 걸리게 하고 싶은 텍스트를 하나로 합칩니다.
            # 이름, 시대, 요약, 설명, 태그를 모두 포함해야 검색이 잘 됩니다.
            content_text = (
                f"이름: {item['name']}\n"
                f"시대: {item.get('era', '')}\n"
                f"유형: {item.get('entity_type', '')}\n"
                f"요약: {item.get('summary', '')}\n"
                f"설명: {item.get('description', '')}\n"
                f"태그: {', '.join(item.get('tags', []))}"
            )

            # 메타데이터에는 원본 ID와 이름 등을 넣어두어 나중에 매칭하기 쉽게 함
            doc = Document(
                page_content=content_text,
                metadata={
                    "id": item["id"],
                    "name": item["name"],
                    "entity_type": item.get("entity_type", "Unknown")
                }
            )
            documents.append(doc)

        # 3. 벡터 DB에 삽입 (자동으로 임베딩 변환됨)
        if documents:
            self.vector_db = Chroma.from_documents(
                documents=documents,
                embedding=self.embedding_model,
                collection_name="history_collection",
                persist_directory=PERSIST_DIRECTORY
            )
            print("✅ 벡터 DB 동기화 완료!")

    def search(self, query: str, top_k: int = 3):
        """
        유사도 검색 수행
        """
        # 유사도 점수와 함께 반환 (score가 낮을수록 유사함 - 거리 기반일 경우)
        results = self.vector_db.similarity_search_with_score(query, k=top_k)
        return results

# 싱글톤 인스턴스
vector_store = HistoryVectorStore()