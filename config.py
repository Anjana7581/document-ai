import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _resolve(value):
    p = Path(value)
    return p if p.is_absolute() else (BASE_DIR / p).resolve()


class Config:
    def __init__(self, **overrides):
        e = os.environ.get
        values = {
            "FLASK_HOST": e("FLASK_HOST", "127.0.0.1"),
            "FLASK_PORT": int(e("FLASK_PORT", "5000")),
            "FLASK_DEBUG": e("FLASK_DEBUG", "false").lower() == "true",
            "OLLAMA_BASE_URL": e("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            "LLM_MODEL": e("LLM_MODEL", "qwen2.5:3b"),
            "EMBEDDING_MODEL": e("EMBEDDING_MODEL", "nomic-embed-text"),
            "DOCUMENT_STORAGE_PATH": e("DOCUMENT_STORAGE_PATH", "./storage/documents"),
            "VECTOR_DB_PATH": e("VECTOR_DB_PATH", "./storage/vector_db"),
            "CHUNK_SIZE": int(e("CHUNK_SIZE", "800")),
            "CHUNK_OVERLAP": int(e("CHUNK_OVERLAP", "120")),
            "TOP_K": int(e("TOP_K", "5")),
            "MAX_UPLOAD_MB": int(e("MAX_UPLOAD_MB", "25")),
            "LLM_TIMEOUT_SECONDS": int(e("LLM_TIMEOUT_SECONDS", "120")),
            "EMBED_TIMEOUT_SECONDS": int(e("EMBED_TIMEOUT_SECONDS", "120")),
            "RELEVANCE_MAX_DISTANCE": float(e("RELEVANCE_MAX_DISTANCE", "0.9")),
            "API_KEY": e("API_KEY", "").strip(),
        }
        values.update(overrides)
        for key, val in values.items():
            setattr(self, key, val)
        self.DOCUMENT_STORAGE_PATH = _resolve(self.DOCUMENT_STORAGE_PATH)
        self.VECTOR_DB_PATH = _resolve(self.VECTOR_DB_PATH)
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
