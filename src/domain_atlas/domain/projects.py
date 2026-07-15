"""Domain project models and repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class DomainProject:
    id: int
    name: str
    goal: str
    level: str
    language: str
    interaction_mode: str
    status: str
    build_status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CreateDomainProject:
    name: str
    goal: str = ""
    level: str = "beginner"
    language: str = "zh"
    interaction_mode: str = "guided"


class DomainProjectRepository:
    """SQLite-backed repository for domain projects."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(self, payload: CreateDomainProject) -> DomainProject:
        name = payload.name.strip()
        if not name:
            raise ValueError("Domain project name is required.")

        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO domain_projects (name, goal, level, language, interaction_mode)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    payload.goal.strip(),
                    payload.level.strip() or "beginner",
                    payload.language.strip() or "zh",
                    _normalize_interaction_mode(payload.interaction_mode),
                ),
            )
            project_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM domain_projects WHERE id = ?",
                (project_id,),
            ).fetchone()

        return _row_to_project(row)

    def list_recent(self) -> list[DomainProject]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM domain_projects
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [_row_to_project(row) for row in rows]

    def get(self, project_id: int) -> DomainProject | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM domain_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return _row_to_project(row) if row else None

    def update_build_status(self, project_id: int, build_status: str) -> DomainProject:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE domain_projects
                SET build_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (build_status, project_id),
            )
            row = connection.execute(
                "SELECT * FROM domain_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return _row_to_project(row)


def _row_to_project(row) -> DomainProject:
    return DomainProject(
        id=int(row["id"]),
        name=str(row["name"]),
        goal=str(row["goal"]),
        level=str(row["level"]),
        language=str(row["language"]),
        interaction_mode=str(row["interaction_mode"]),
        status=str(row["status"]),
        build_status=str(row["build_status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _normalize_interaction_mode(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in {"guided", "expert"} else "guided"
