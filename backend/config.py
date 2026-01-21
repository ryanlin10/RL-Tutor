import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    # Database - Railway provides DATABASE_URL, SQLite for local dev
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///rl_tutor.db"
    )
    # Railway uses postgres:// but SQLAlchemy needs postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # Groq API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "gpt-oss-120b")  # Multimodal model
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.getenv("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT = "1000 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    # RAG Configuration
    RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector_store")
    LECTURE_NOTES_PATH = os.getenv("LECTURE_NOTES_PATH", "./data/lecture_notes")
