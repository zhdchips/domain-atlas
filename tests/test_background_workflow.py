from __future__ import annotations

import threading
import time

import pytest

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.workflow.background import BackgroundWorkflowRunner, WorkflowConflictError


def test_background_runner_persists_state_and_rejects_conflicting_project_work(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Agent"))
    repository = WorkflowRepository(database_path)
    runner = BackgroundWorkflowRunner(repository)
    release = threading.Event()

    def work(run_id: int) -> None:
        repository.record_step(run_id, step_name="compile_context", status="running")
        release.wait(timeout=2)
        repository.record_step(run_id, step_name="compile_context", status="completed")

    run_id = runner.submit(project_id=project.id, workflow_name="knowledge_build", work=work)

    with pytest.raises(WorkflowConflictError):
        runner.submit(project_id=project.id, workflow_name="guided_autopilot", work=work)

    assert repository.get_status(run_id) in {"queued", "running"}
    release.set()
    _wait_for_status(repository, run_id, "completed")
    assert repository.list_for_project(project.id)[0].steps[-1].status == "completed"


def test_interrupted_runs_are_readable_after_restart(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Agent"))
    repository = WorkflowRepository(database_path)
    run_id = repository.start_run(project.id, "knowledge_build", status="running")

    assert repository.interrupt_active_runs() == 1

    run = repository.list_for_project(project.id)[0]
    assert run.id == run_id
    assert run.status == "interrupted"
    assert "服务重启前任务未完成" in run.error
    assert run.steps[-1].step_name == "interrupted"


def _wait_for_status(repository: WorkflowRepository, run_id: int, expected: str) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if repository.get_status(run_id) == expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"run {run_id} did not become {expected}")
