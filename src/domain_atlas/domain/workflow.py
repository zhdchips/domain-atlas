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

    def start_run(self, project_id: int, workflow_name: str) -> int:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO workflow_runs (project_id, workflow_name, status)
                VALUES (?, ?, 'running')
                """,
                (project_id, workflow_name),
            )
        return int(cursor.lastrowid)

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
