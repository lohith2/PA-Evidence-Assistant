from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str

    # Pinecone
    pinecone_api_key: str
    pinecone_index: str = "prior-auth-agent"
    pinecone_environment: str = "us-east-1"

    # Voyage AI
    voyage_api_key: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Postgres
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prior_auth"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/prior_auth"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5174,http://127.0.0.1:3000,http://127.0.0.1:5174"

    # Model names
    model_reasoning: str = "gemini-2.5-pro"
    model_fast: str = "gemini-2.5-flash"

    # Agent config
    confidence_threshold_high: float = 0.75
    confidence_threshold_low: float = 0.40
    quality_threshold: float = 0.70
    max_quality_loops: int = 2

    # Retrieval
    top_k_policy: int = 5
    top_k_evidence: int = 7
    bm25_weight: float = 0.4
    semantic_weight: float = 0.6

    class Config:
        env_file = (".env", "../.env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
