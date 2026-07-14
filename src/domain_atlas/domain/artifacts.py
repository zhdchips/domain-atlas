"""Knowledge artifact persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class WikiPage:
    id: int
    project_id: int
    title: str
    topic_path: str
    summary: str
    body_markdown: str
    citations: list[str]


@dataclass(frozen=True)
class LearningModule:
    id: int
    project_id: int
    stage: int
    title: str
    objectives: list[str]
    readings: list[str]
    key_concepts: list[str]
    check_questions: list[str]
    practice_task: str
    citations: list[str]


class KnowledgeArtifactRepository:
    """Persist generated knowledge artifacts for a project."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def replace_project_artifacts(self, project_id: int, payload: dict[str, Any]) -> None:
        with connect(self.database_path) as connection:
            for table in (
                "source_profiles",
                "concept_edges",
                "concepts",
                "wiki_pages",
                "learning_modules",
            ):
                connection.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))

            for profile in _list(payload.get("source_profiles")):
                connection.execute(
                    """
                    INSERT INTO source_profiles (
                        project_id, source_id, summary, authority_note, coverage_note, citations_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        int(profile.get("source_id") or 0),
                        _str(profile.get("summary")),
                        _str(profile.get("authority_note")),
                        _str(profile.get("coverage_note")),
                        _json_list(profile.get("citations")),
                    ),
                )

            for concept in _list(payload.get("concepts")):
                connection.execute(
                    """
                    INSERT INTO concepts (
                        project_id, name, definition, prerequisites_json, related_json, citations_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        _str(concept.get("name")),
                        _str(concept.get("definition")),
                        _json_list(concept.get("prerequisites")),
                        _json_list(concept.get("related")),
                        _json_list(concept.get("citations")),
                    ),
                )

            for edge in _list(payload.get("concept_edges")):
                connection.execute(
                    """
                    INSERT INTO concept_edges (
                        project_id, source_concept, target_concept, relation, citations_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        _str(edge.get("source")),
                        _str(edge.get("target")),
                        _str(edge.get("relation")) or "related",
                        _json_list(edge.get("citations")),
                    ),
                )

            for page in _list(payload.get("wiki_pages")):
                connection.execute(
                    """
                    INSERT INTO wiki_pages (
                        project_id, title, topic_path, summary, body_markdown, citations_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        _str(page.get("title")),
                        _str(page.get("topic_path")) or _str(page.get("title")),
                        _str(page.get("summary")),
                        _str(page.get("body_markdown")),
                        _json_list(page.get("citations")),
                    ),
                )

            for module in _list(payload.get("learning_modules")):
                connection.execute(
                    """
                    INSERT INTO learning_modules (
                        project_id,
                        stage,
                        title,
                        objectives_json,
                        readings_json,
                        key_concepts_json,
                        check_questions_json,
                        practice_task,
                        citations_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        int(module.get("stage") or 0),
                        _str(module.get("title")),
                        _json_list(module.get("objectives")),
                        _json_list(module.get("readings")),
                        _json_list(module.get("key_concepts")),
                        _json_list(module.get("check_questions")),
                        _str(module.get("practice_task")),
                        _json_list(module.get("citations")),
                    ),
                )

    def list_wiki_pages(self, project_id: int) -> list[WikiPage]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM wiki_pages WHERE project_id = ? ORDER BY topic_path ASC, id ASC",
                (project_id,),
            ).fetchall()
        return [
            WikiPage(
                id=int(row["id"]),
                project_id=int(row["project_id"]),
                title=str(row["title"]),
                topic_path=str(row["topic_path"]),
                summary=str(row["summary"]),
                body_markdown=str(row["body_markdown"]),
                citations=json.loads(str(row["citations_json"] or "[]")),
            )
            for row in rows
        ]

    def list_learning_modules(self, project_id: int) -> list[LearningModule]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM learning_modules WHERE project_id = ? ORDER BY stage ASC, id ASC",
                (project_id,),
            ).fetchall()
        return [
            LearningModule(
                id=int(row["id"]),
                project_id=int(row["project_id"]),
                stage=int(row["stage"]),
                title=str(row["title"]),
                objectives=json.loads(str(row["objectives_json"] or "[]")),
                readings=json.loads(str(row["readings_json"] or "[]")),
                key_concepts=json.loads(str(row["key_concepts_json"] or "[]")),
                check_questions=json.loads(str(row["check_questions_json"] or "[]")),
                practice_task=str(row["practice_task"]),
                citations=json.loads(str(row["citations_json"] or "[]")),
            )
            for row in rows
        ]

    def count_wiki_pages(self, project_id: int) -> int:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM wiki_pages WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["count"])


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _json_list(value: Any) -> str:
    items = value if isinstance(value, list) else []
    return json.dumps([str(item) for item in items], ensure_ascii=False)
