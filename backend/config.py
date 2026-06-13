"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings."""

    # API Keys
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # Security
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "default-dev-key-change-in-production!!")
    allowed_origins: list[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    rate_limit_uploads: int = int(os.getenv("RATE_LIMIT_UPLOADS", "30"))
    rate_limit_chat: int = int(os.getenv("RATE_LIMIT_CHAT", "60"))

    # Storage
    base_dir: Path = Path(__file__).parent
    storage_path: Path = Path(os.getenv("STORAGE_PATH", "./storage"))
    chroma_path: Path = Path(os.getenv("CHROMA_PATH", "./storage/chromadb"))
    documents_path: Path = storage_path / "documents"
    page_images_path: Path = storage_path / "page_images"

    # App
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = app_env == "development"

    # Embedding model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 50

    # LLM
    llm_model: str = "gemini-2.0-flash"

    def ensure_directories(self):
        """Create required storage directories."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.page_images_path.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
settings.ensure_directories()
