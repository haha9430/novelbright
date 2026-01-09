import logging
import chromadb
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from app.core.settings import chromadb_settings

logger = logging.getLogger("chroma")


class ChromaDBConnectionManager:
    _instance: Optional['ChromaDBConnectionManager'] = None
    _client: Optional[chromadb.HttpClient] = None
    _collections_cache: Dict[str, Any] = {}
    _last_health_check: float = 0
    _health_check_interval: float = 30.0
    _max_retries: int = 3
    _retry_delay: float = 1.0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_connection()
    
    def _initialize_connection(self):
        for attempt in range(self._max_retries):
            try:
                self._client = chromadb.HttpClient(
                    host=chromadb_settings.host, 
                    port=chromadb_settings.port
                )
                self._test_connection()
                logger.info(f"ChromaDB connection established: {chromadb_settings.host}:{chromadb_settings.port}")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Failed to connect to ChromaDB after {self._max_retries} attempts")
                    raise ConnectionError(f"Could not establish ChromaDB connection: {e}")
    
    def _test_connection(self):
        self._client.heartbeat()
        self._last_health_check = time.time()
    
    def _ensure_healthy_connection(self):
        current_time = time.time()
        if current_time - self._last_health_check > self._health_check_interval:
            try:
                self._test_connection()
            except Exception as e:
                logger.warning(f"Health check failed, reconnecting: {e}")
                self._client = None
                self._collections_cache.clear()
                self._initialize_connection()
    
    @property
    def client(self) -> chromadb.HttpClient:
        self._ensure_healthy_connection()
        return self._client
    
    def get_collection(self, collection_name: str = None):
        name = collection_name or chromadb_settings.collection_name
        
        if name not in self._collections_cache:
            try:
                collection = self.client.get_or_create_collection(
                    name=name,
                    metadata={"description": "Upstage Solar2 embeddings collection"}
                )
                self._collections_cache[name] = collection
                logger.debug(f"Collection '{name}' cached")
            except Exception as e:
                logger.error(f"Failed to get collection '{name}': {e}")
                raise
        
        return self._collections_cache[name]
    
    def clear_cache(self):
        self._collections_cache.clear()
        logger.info("Collection cache cleared")
    
    @contextmanager
    def get_connection(self):
        try:
            yield self.client
        except Exception as e:
            logger.error(f"Error during ChromaDB operation: {e}")
            raise
        finally:
            pass
    
    def close(self):
        if self._client:
            self._collections_cache.clear()
            self._client = None
            logger.info("ChromaDB connection closed")


_connection_manager = ChromaDBConnectionManager()


def get_chroma_client() -> chromadb.HttpClient:
    """ChromaDB 클라이언트를 반환하는 의존성 함수"""
    return _connection_manager.client


def get_chroma_collection(collection_name: str = None):
    """ChromaDB 컬렉션을 반환하는 의존성 함수"""
    return _connection_manager.get_collection(collection_name)


def get_connection_manager() -> ChromaDBConnectionManager:
    """ChromaDB 연결 매니저를 반환하는 함수"""
    return _connection_manager