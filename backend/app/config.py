"""Application configuration loaded from environment variables or a .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central settings object. Every value can be overridden via environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Synapse"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Database
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'synapse.db'}"

    # LLM provider (any OpenAI-compatible API works via base_url).
    # Defaults target Google Gemini's free tier via its OpenAI-compatible
    # endpoint. For OpenAI itself set OPENAI_BASE_URL=https://api.openai.com/v1
    # and OpenAI model names (see .env.example).
    # The key is read from GEMINI_API_KEY, OPENAI_API_KEY or LLM_API_KEY.
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"
        ),
    )
    openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    chat_model: str = "gemini-3.5-flash"
    utility_model: str = "gemini-2.5-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    available_models: str = "gemini-3.5-flash,gemini-2.5-flash,gemini-2.5-flash-lite"
    max_agent_iterations: int = 6
    request_timeout_seconds: int = 90

    # Memory
    history_window_messages: int = 16
    summarize_after_messages: int = 24

    # RAG
    vector_store: str = "chroma"  # "chroma" or "memory"
    chroma_dir: str = str(BASE_DIR / "data" / "chroma")
    chunk_size: int = 900
    chunk_overlap: int = 150
    dense_top_k: int = 20
    bm25_top_k: int = 20
    fused_top_k: int = 10
    final_top_k: int = 5
    rerank_enabled: bool = True
    max_upload_mb: int = 10

    # Rate limiting (requests per window)
    rate_limit_auth: int = 20
    rate_limit_chat: int = 40
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def model_list(self) -> list[str]:
        return [m.strip() for m in self.available_models.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
