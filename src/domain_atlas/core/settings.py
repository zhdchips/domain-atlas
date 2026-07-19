"""Application settings for Domain Atlas."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment and ignored `.env` files."""

    app_name: str = "Domain Atlas"
    default_language: str = "zh"
    data_dir: Path = Path("data")
    deployment_mode: Literal["local", "public_demo", "private_owner"] = "local"
    public_demo_mode: bool = False

    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_callback_url: str = ""
    owner_github_user_id: int | None = None
    session_secret: str = ""
    session_cookie_name: str = "domain_atlas_session"
    session_cookie_secure: bool = True
    session_ttl_hours: int = 24 * 30
    oauth_state_ttl_minutes: int = 10

    search_provider: str = "exa"
    exa_api_key: str = ""
    search_max_results: int = 12
    search_display_results: int = 8
    search_timeout_seconds: float = 30.0
    search_max_retries: int = 2
    embedding_timeout_seconds: float = 45.0
    embedding_max_retries: int = 2
    url_fetch_timeout_seconds: float = 30.0
    url_fetch_max_retries: int = 2
    provider_retry_base_delay_seconds: float = 1.0
    provider_retry_jitter_seconds: float = 0.2

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

    @model_validator(mode="after")
    def resolve_deployment_mode(self) -> Settings:
        """Keep the original public flag compatible without weakening explicit modes."""
        explicit_mode = "deployment_mode" in self.model_fields_set
        explicit_legacy = "public_demo_mode" in self.model_fields_set
        if explicit_mode and explicit_legacy:
            expected_public = self.deployment_mode == "public_demo"
            if self.public_demo_mode != expected_public:
                raise ValueError("DEPLOYMENT_MODE conflicts with PUBLIC_DEMO_MODE.")
        elif not explicit_mode and self.public_demo_mode:
            self.deployment_mode = "public_demo"
        self.public_demo_mode = self.deployment_mode == "public_demo"
        return self

    @property
    def private_owner_mode(self) -> bool:
        """Whether the app requires its configured single owner."""
        return self.deployment_mode == "private_owner"

    def validate_private_auth(self) -> None:
        """Fail early when a private deployment cannot authenticate its owner."""
        if not self.private_owner_mode:
            return
        missing: list[str] = []
        if not self.github_oauth_client_id.strip():
            missing.append("GITHUB_OAUTH_CLIENT_ID")
        if not self.github_oauth_client_secret.strip():
            missing.append("GITHUB_OAUTH_CLIENT_SECRET")
        if not self.github_oauth_callback_url.strip():
            missing.append("GITHUB_OAUTH_CALLBACK_URL")
        if self.owner_github_user_id is None:
            missing.append("OWNER_GITHUB_USER_ID")
        if len(self.session_secret) < 32:
            missing.append("SESSION_SECRET (at least 32 characters)")
        if missing:
            raise ValueError("Private owner authentication is not configured: " + ", ".join(missing))
        if self.session_ttl_hours <= 0 or self.oauth_state_ttl_minutes <= 0:
            raise ValueError("Private owner authentication TTL values must be positive.")

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
