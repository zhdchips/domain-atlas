from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_intake_assessment(monkeypatch):
    """Keep default regressions deterministic even when a developer .env has provider keys."""
    monkeypatch.setenv("INTAKE_LLM_ASSESSMENT_ENABLED", "false")
