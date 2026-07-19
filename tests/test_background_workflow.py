from __future__ import annotations

import threading
import time
import sqlite3

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

    run_id = runner.submit(
        project_id=project.id,
        workflow_name="knowledge_build",
        input_payload={"reason": "initial"},
        work=work,
    )

    with pytest.raises(WorkflowConflictError):
        runner.submit(project_id=project.id, workflow_name="guided_autopilot", work=work)

    assert repository.get_status(run_id) in {"queued", "running"}
    release.set()
    _wait_for_status(repository, run_id, "completed")
    persisted = repository.list_for_project(project.id)[0]
    assert persisted.steps[-1].status == "completed"
    assert persisted.input == {"reason": "initial"}


def test_interrupted_runs_are_readable_after_restart(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Agent"))
    repository = WorkflowRepository(database_path)
    run_id = repository.start_run(
        project.id,
        "knowledge_build",
        status="running",
        input_payload={},
    )

    assert repository.interrupt_active_runs() == 1

    run = repository.list_for_project(project.id)[0]
    assert run.id == run_id
    assert run.status == "interrupted"
    assert "服务重启前任务未完成" in run.error
    assert run.steps[-1].step_name == "interrupted"
    assert run.can_retry is True


def test_retry_run_keeps_original_history_and_server_side_input(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Agent"))
    repository = WorkflowRepository(database_path)
    original_id = repository.start_run(
        project.id,
        "source_ingestion",
        input_payload={"source_id": 17},
    )
    repository.record_step(
        original_id,
        step_name="load",
        status="failed",
        error="network unavailable",
    )
    repository.fail_run(original_id, "network unavailable")

    retry_id = repository.start_run(
        project.id,
        "source_ingestion",
        input_payload={"source_id": 17},
        retry_of_run_id=original_id,
    )
    repository.finish_run(retry_id)

    original = repository.get(original_id)
    retry = repository.get(retry_id)
    assert original is not None
    assert retry is not None
    assert original.error == "network unavailable"
    assert original.steps[0].error == "network unavailable"
    assert retry.retry_of_run_id == original_id
    assert retry.input == {"source_id": 17}


def test_existing_workflow_run_table_is_migrated_for_retry_metadata(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                workflow_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(workflow_runs)")}
    assert "input_json" in columns
    assert "retry_of_run_id" in columns


def _wait_for_status(repository: WorkflowRepository, run_id: int, expected: str) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if repository.get_status(run_id) == expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"run {run_id} did not become {expected}")
