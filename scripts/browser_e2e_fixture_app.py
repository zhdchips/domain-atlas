"""Deterministic app factory used only by the Playwright regression script."""

from __future__ import annotations

import time

from domain_atlas.core.settings import Settings
from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.web.app import create_app as create_production_app


class BrowserAutopilotRunner:
    """Leave a short observable running window, then persist a successful guided run."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, project_id: int, *, run_id: int | None = None):
        repository = WorkflowRepository(self.settings.database_path)
        if run_id is None:
            run_id = repository.start_run(project_id, "guided_autopilot")
        repository.record_step(run_id, step_name="discover_candidates", status="running")
        repository.record_step(
            run_id,
            step_name="provider_retry",
            status="running",
            output={
                "phase": "retrying",
                "provider": "Exa",
                "operation": "搜索",
                "category": "server_error",
                "attempts": 1,
                "max_attempts": 3,
                "retryable": True,
                "recovery_message": "服务暂时不可用，请稍后重试。",
                "next_delay_seconds": 0.2,
            },
        )
        time.sleep(0.45)
        repository.record_step(
            run_id,
            step_name="discover_candidates",
            status="completed",
            output={"candidate_count": 4},
        )
        repository.record_step(
            run_id,
            step_name="provider_retry",
            status="completed",
            output={
                "phase": "recovered",
                "provider": "Exa",
                "operation": "搜索",
                "category": "server_error",
                "attempts": 1,
                "max_attempts": 3,
                "retryable": True,
                "recovery_message": "服务暂时不可用，请稍后重试。",
                "next_delay_seconds": 0,
            },
        )
        repository.record_step(
            run_id,
            step_name="ingest_sources",
            status="completed",
            output={
                "completed": 2,
                "total": 4,
                "success_count": 2,
                "attempted_count": 4,
                "failed_count": 2,
                "minimum_build_sources": 2,
                "terminal_reason": "minimum_independent_sources_reached",
                "successful_families": ["fixture:official", "fixture:institution"],
            },
        )
        repository.record_step(
            run_id,
            step_name="build_knowledge",
            status="completed",
            output={"status": "completed"},
        )
        repository.finish_run(run_id)
        DomainProjectRepository(self.settings.database_path).update_build_status(project_id, "completed")


def create_app():
    settings = Settings()
    return create_production_app(
        settings,
        autopilot_runner=BrowserAutopilotRunner(settings),
    )
