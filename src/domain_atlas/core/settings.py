"""Application settings for Domain Atlas."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment and ignored `.env` files."""

    app_name: str = "Domain Atlas"
    default_language: str = "zh"
    data_dir: Path = Path("data")

    search_provider: str = "exa"
    exa_api_key: str = ""
    search_max_results: int = 12
    search_display_results: int = 8
    search_timeout_seconds: float = 30.0
    search_max_retries: int = 2

    llm_provider: str = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    chat_model: str = "deepseek-chat"
    chat_max_tokens: int = 12_000
    llm_timeout_seconds: float = 180.0
    llm_max_retries: int = 2
    intake_llm_assessment_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "INTAKE_LLM_ASSESSMENT_ENABLED",
            "INTAKE_LLM_SUGGESTIONS_ENABLED",
        ),
    )
    intake_llm_timeout_seconds: float = 15.0
    intake_llm_min_confidence: float = 0.60

    embedding_provider: str = "dashscope"
    embedding_base_url: str = ""
    embedding_api_key: str = Field(default="", validation_alias="EMBEDDING_API_KEY")
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_path(self) -> Path:
        """SQLite database path under the local data directory."""
        return self.data_dir / "domain_atlas.sqlite3"

    @property
    def chroma_path(self) -> Path:
        """Chroma persistence directory under the local data directory."""
        return self.data_dir / "chroma"

    @property
    def uploads_path(self) -> Path:
        """Uploaded source file storage directory."""
        return self.data_dir / "uploads"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
