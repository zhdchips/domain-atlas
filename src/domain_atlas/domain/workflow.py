"""Workflow run persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


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
