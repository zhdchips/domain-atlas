"""Private-owner fixture app with a local fake OAuth redirect."""

from __future__ import annotations

import time
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from domain_atlas.auth import GitHubIdentity
from domain_atlas.core.settings import Settings
from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.qa import QARepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.web.app import create_app as create_production_app
from scripts.browser_e2e_wiki_layout import _create_wiki_fixture


class BrowserOAuthProvider:
    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        redirect_uri: str,
    ) -> str:
        return "/test-oauth/authorize?" + urlencode(
            {"state": state, "challenge": code_challenge}
        )

    def fetch_identity(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GitHubIdentity:
        if code != "browser-owner" or not code_verifier:
            raise RuntimeError("Fixture OAuth request is invalid.")
        return GitHubIdentity(user_id=4242, login="browser-owner")


class BrowserPrivateAutopilot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, project_id: int, *, run_id: int | None = None):
        repository = WorkflowRepository(self.settings.database_path)
        assert run_id is not None
        repository.record_step(run_id, step_name="discover_candidates", status="running")
        time.sleep(0.45)
        repository.record_step(
            run_id,
            step_name="discover_candidates",
            status="completed",
            output={"candidate_count": 3},
        )
        repository.record_step(
            run_id,
            step_name="ingest_sources",
            status="completed",
            output={"completed": 2, "total": 2, "success_count": 2},
        )
        repository.record_step(
            run_id,
            step_name="build_knowledge",
            status="completed",
            output={"status": "completed"},
        )
        DomainProjectRepository(self.settings.database_path).update_build_status(
            project_id, "completed"
        )


def create_app() -> FastAPI:
    settings = Settings()
    app = create_production_app(
        settings,
        oauth_provider=BrowserOAuthProvider(),
        autopilot_runner=BrowserPrivateAutopilot(settings),
    )
    project_ids = _create_wiki_fixture(settings)
    project_id = project_ids[0]
    QARepository(settings.database_path).create(
        project_id=project_id,
        question="私有知识库如何保持可溯源？",
        answer="通过 Wiki 引用和 Source provenance 回到原始证据。",
        citations=["W:provenance#1"],
        source_provenance=["S1-C1"],
        evidence_status="sufficient",
    )

    @app.get("/test-oauth/authorize")
    def fixture_authorize(state: str, challenge: str) -> RedirectResponse:
        if not state or not challenge:
            raise RuntimeError("Fixture OAuth state or challenge is missing.")
        return RedirectResponse(
            url="/auth/callback?" + urlencode({"code": "browser-owner", "state": state}),
            status_code=303,
        )

    return app
