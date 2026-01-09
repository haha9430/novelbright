import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class BaseSettings:
    """Base settings class for environment variable management"""
    
    def __init__(self):
        self._load_settings()
    
    def _load_settings(self):
        pass
    
    def get_env(self, key: str, default: Optional[str] = None, required: bool = False) -> str:
        """Get environment variable with optional validation"""
        value = os.getenv(key, default)
        if required and not value:
            raise ValueError(f"{key} environment variable is required")
        return value


class UpstageSettings(BaseSettings):
    """Upstage API settings"""
    
    def __init__(self):
        super().__init__()
        self.api_key = self.get_env("UPSTAGE_API_KEY", required=True)
        self.base_url = self.get_env("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
        self.embedding_model = self.get_env("UPSTAGE_EMBEDDING_MODEL", "solar-embedding-1-large-query")
        self.chat_model = self.get_env("UPSTAGE_CHAT_MODEL", "solar-1-mini-chat")


class ChromaDBSettings(BaseSettings):
    """ChromaDB settings"""
    
    def __init__(self):
        super().__init__()
        self.host = self.get_env("CHROMA_HOST", "localhost")
        self.port = int(self.get_env("CHROMA_PORT", "8800"))
        self.collection_name = self.get_env("CHROMA_COLLECTION_NAME", "upstage_embeddings")


upstage_settings = UpstageSettings()
chromadb_settings = ChromaDBSettings()