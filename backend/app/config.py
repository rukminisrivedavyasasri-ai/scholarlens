import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "ScholarLens Evidence Workspace"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./scholarlens.db")
    
    # JWT Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", "scholarlens_dev_secret_key_please_change_in_production_92817")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # File Storage & Limits
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./storage")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
    ALLOWED_FILE_TYPES: str = os.getenv("ALLOWED_FILE_TYPES", "application/pdf")
    
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    
    # Retrieval & Relevance Abstention Threshold
    # Scores below this threshold represent weak similarity and trigger abstention
    QA_RELEVANCE_THRESHOLD: float = float(os.getenv("QA_RELEVANCE_THRESHOLD", "0.38"))

settings = Settings()
