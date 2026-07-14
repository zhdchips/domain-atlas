"""QA record persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class QARecord:
    id: int
    project_id: int
    question: str
    answer: str
    citations: list[str]
    evidence_status: str
    created_at: str


class QARepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(
        self,
        *,
        project_id: int,
        question: str,
        answer: str,
        citations: list[str],
        evidence_status: str,
    ) -> QARecord:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO qa_records (
                    project_id, question, answer, citations_json, evidence_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    question.strip(),
                    answer.strip(),
                    json.dumps(citations, ensure_ascii=False),
                    evidence_status,
                ),
            )
            record_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM qa_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        return _row_to_record(row)

    def list_for_project(self, project_id: int) -> list[QARecord]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM qa_records
                WHERE project_id = ?
                ORDER BY id DESC
                """,
                (project_id,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]


def _row_to_record(row) -> QARecord:
    return QARecord(
        id=int(row["id"]),
        project_id=int(row["project_id"]),
        question=str(row["question"]),
        answer=str(row["answer"]),
        citations=json.loads(str(row["citations_json"] or "[]")),
        evidence_status=str(row["evidence_status"]),
        created_at=str(row["created_at"]),
    )
