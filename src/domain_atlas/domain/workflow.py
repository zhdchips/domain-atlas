"""Workflow run persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class WorkflowStep:
    id: int
    run_id: int
    step_name: str
    status: str
    output: dict[str, Any]
    error: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    project_id: int
    workflow_name: str
    status: str
    error: str
    created_at: str
    updated_at: str
    steps: list[WorkflowStep]


class WorkflowRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def start_run(self, project_id: int, workflow_name: str, *, status: str = "running") -> int:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO workflow_runs (project_id, workflow_name, status)
                VALUES (?, ?, ?)
                """,
                (project_id, workflow_name, status),
            )
        return int(cursor.lastrowid)

    def mark_running(self, run_id: int) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE workflow_runs
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'queued'
                """,
                (run_id,),
            )

    def record_step(
        self,
        run_id: int,
        *,
        step_name: str,
        status: str,
        output: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO workflow_steps (run_id, step_name, status, output_json, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_name,
                    status,
                    json.dumps(output or {}, ensure_ascii=False),
                    error,
                ),
            )

    def finish_run(self, run_id: int) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE workflow_runs
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (run_id,),
            )

    def fail_run(self, run_id: int, error: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE workflow_runs
                SET status = 'failed', error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error, run_id),
            )

    def has_active_run(self, project_id: int) -> bool:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT 1 FROM workflow_runs
                WHERE project_id = ? AND status IN ('queued', 'running')
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return row is not None

    def get_status(self, run_id: int) -> str | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT status FROM workflow_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return str(row["status"]) if row else None

    def interrupt_active_runs(self) -> int:
        """Close tasks from a previous process that cannot resume locally."""
        message = "服务重启前任务未完成，已标记为中断；请重新发起。"
        with connect(self.database_path) as connection:
            active_rows = connection.execute(
                """
                SELECT id FROM workflow_runs
                WHERE status IN ('queued', 'running')
                """
            ).fetchall()
            for row in active_rows:
                connection.execute(
                    """
                    UPDATE workflow_runs
                    SET status = 'interrupted', error = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (message, int(row["id"])),
                )
                connection.execute(
                    """
                    INSERT INTO workflow_steps (run_id, step_name, status, output_json, error)
                    VALUES (?, 'interrupted', 'interrupted', '{}', ?)
                    """,
                    (int(row["id"]), message),
                )
        return len(active_rows)

    def list_for_project(self, project_id: int, *, limit: int = 5) -> list[WorkflowRun]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM workflow_runs
                WHERE project_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
            run_ids = [int(row["id"]) for row in rows]
            steps_by_run: dict[int, list[WorkflowStep]] = {run_id: [] for run_id in run_ids}
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                step_rows = connection.execute(
                    f"""
                    SELECT *
                    FROM workflow_steps
                    WHERE run_id IN ({placeholders})
                    ORDER BY id ASC
                    """,
                    run_ids,
                ).fetchall()
                for step_row in step_rows:
                    step = _row_to_step(step_row)
                    steps_by_run.setdefault(step.run_id, []).append(step)
        return [_row_to_run(row, steps_by_run.get(int(row["id"]), [])) for row in rows]


def _row_to_run(row, steps: list[WorkflowStep]) -> WorkflowRun:
    return WorkflowRun(
        id=int(row["id"]),
        project_id=int(row["project_id"]),
        workflow_name=str(row["workflow_name"]),
        status=str(row["status"]),
        error=str(row["error"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        steps=steps,
    )


def _row_to_step(row) -> WorkflowStep:
    return WorkflowStep(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        step_name=str(row["step_name"]),
        status=str(row["status"]),
        output=json.loads(str(row["output_json"] or "{}")),
        error=str(row["error"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
