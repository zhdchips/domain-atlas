"""Small persisted background runner for the single-process MVP."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from domain_atlas.domain.workflow import WorkflowRepository


class WorkflowConflictError(RuntimeError):
    """Raised when a project already has a long-running operation."""


class BackgroundWorkflowRunner:
    """Launch local threads while keeping SQLite as the observable task record."""

    def __init__(
        self,
        repository: WorkflowRepository,
        *,
        work_guard: Callable[[], AbstractContextManager[None]] | None = None,
    ) -> None:
        self.repository = repository
        self._lock = threading.Lock()
        self.work_guard = work_guard or nullcontext

    def submit(
        self,
        *,
        project_id: int,
        workflow_name: str,
        work: Callable[[int], object],
    ) -> int:
        with self._lock:
            if self.repository.has_active_run(project_id):
                raise WorkflowConflictError("已有任务正在执行，请等待当前任务完成后再试。")
            run_id = self.repository.start_run(project_id, workflow_name, status="queued")

        thread = threading.Thread(
            target=self._run,
            args=(run_id, work),
            name=f"domain-atlas-{workflow_name}-{run_id}",
            daemon=True,
        )
        thread.start()
        return run_id

    def _run(self, run_id: int, work: Callable[[int], object]) -> None:
        self.repository.mark_running(run_id)
        try:
            with self.work_guard():
                work(run_id)
        except Exception as exc:
            if self.repository.get_status(run_id) in {"queued", "running"}:
                self.repository.record_step(
                    run_id,
                    step_name="workflow",
                    status="failed",
                    error=str(exc),
                )
                self.repository.fail_run(run_id, str(exc))
            return
        if self.repository.get_status(run_id) in {"queued", "running"}:
            self.repository.finish_run(run_id)
