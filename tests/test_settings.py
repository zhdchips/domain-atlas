from __future__ import annotations

from pathlib import Path

from domain_atlas.core.settings import Settings


def test_settings_paths_are_under_data_dir(tmp_path):
    settings = Settings(data_dir=tmp_path)

    assert settings.database_path == tmp_path / "domain_atlas.sqlite3"
    assert settings.chroma_path == tmp_path / "chroma"
    assert settings.uploads_path == tmp_path / "uploads"


def test_provider_defaults_match_mvp_contract():
    settings = Settings()

    assert settings.search_provider == "exa"
    assert settings.search_max_results == 12
    assert settings.search_display_results == 8
    assert settings.search_timeout_seconds == 30.0
    assert settings.search_max_retries == 2
    assert settings.llm_provider == "deepseek"
    assert settings.chat_model == "deepseek-chat"
    assert settings.chat_max_tokens == 12_000
    assert settings.llm_timeout_seconds == 180.0
    assert settings.llm_max_retries == 2
    assert settings.embedding_provider == "dashscope"
    assert settings.embedding_model == "text-embedding-v4"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_timeout_seconds == 45.0
    assert settings.embedding_max_retries == 2
    assert settings.url_fetch_timeout_seconds == 30.0
    assert settings.url_fetch_max_retries == 2
    assert settings.provider_retry_base_delay_seconds == 1.0
    assert settings.provider_retry_jitter_seconds == 0.2


def test_intake_assessment_is_enabled_by_default_when_not_explicitly_disabled(monkeypatch):
    monkeypatch.delenv("INTAKE_LLM_ASSESSMENT_ENABLED", raising=False)
    monkeypatch.delenv("INTAKE_LLM_SUGGESTIONS_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.intake_llm_assessment_enabled is True
