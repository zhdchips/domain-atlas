"""Knowledge artifact persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class WikiPage:
    id: int
    project_id: int
    slug: str
    title: str
    topic_path: str
    summary: str
    body_markdown: str
    citations: list[str]
    revision: int


@dataclass(frozen=True)
class WikiSection:
    id: int
    section_uid: str
    project_id: int
    page_id: int
    page_slug: str
    heading: str
    ordinal: int
    body_markdown: str
    citations: list[str]
    source_chunk_uids: list[str]
    source_citation_labels: list[str]
    links: list[str]


@dataclass(frozen=True)
class WikiLink:
    id: int
    project_id: int
    source_page_slug: str
    target_page_slug: str
    link_text: str


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
                "wiki_links",
                "wiki_sections",
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
                title = _str(page.get("title"))
                topic_path = _str(page.get("topic_path")) or title
                slug = _slug(page.get("slug") or topic_path or title)
                page_citations = _string_list(page.get("citations"))
                cursor = connection.execute(
                    """
                    INSERT INTO wiki_pages (
                        project_id, slug, title, topic_path, summary, body_markdown, citations_json, revision
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        slug,
                        title,
                        topic_path,
                        _str(page.get("summary")),
                        _str(page.get("body_markdown")),
                        json.dumps(page_citations, ensure_ascii=False),
                        int(page.get("revision") or 1),
                    ),
                )
                page_id = int(cursor.lastrowid)
                sections = _sections_for_page(page=page, default_citations=page_citations)
                for ordinal, section in enumerate(sections, start=1):
                    heading = _str(section.get("heading")) or title
                    body = _str(section.get("body_markdown")) or _str(section.get("body"))
                    links = _string_list(section.get("links")) or _extract_wikilinks(body)
                    source_labels = _string_list(section.get("source_citation_labels")) or _string_list(
                        section.get("citations")
                    )
                    source_chunk_uids = _string_list(section.get("source_chunk_uids"))
                    citations = _string_list(section.get("citations")) or page_citations
                    section_uid = _str(section.get("section_uid")) or f"{slug}#{ordinal}"
                    connection.execute(
                        """
                        INSERT INTO wiki_sections (
                            section_uid,
                            project_id,
                            page_id,
                            page_slug,
                            heading,
                            ordinal,
                            body_markdown,
                            citations_json,
                            source_chunk_uids_json,
                            source_citation_labels_json,
                            links_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            section_uid,
                            project_id,
                            page_id,
                            slug,
                            heading,
                            ordinal,
                            body,
                            json.dumps(citations, ensure_ascii=False),
                            json.dumps(source_chunk_uids, ensure_ascii=False),
                            json.dumps(source_labels, ensure_ascii=False),
                            json.dumps(links, ensure_ascii=False),
                        ),
                    )
                    for target in links:
                        connection.execute(
                            """
                            INSERT INTO wiki_links (
                                project_id, source_page_slug, target_page_slug, link_text
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (project_id, slug, _slug(target), target),
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
                slug=str(row["slug"]),
                title=str(row["title"]),
                topic_path=str(row["topic_path"]),
                summary=str(row["summary"]),
                body_markdown=str(row["body_markdown"]),
                citations=json.loads(str(row["citations_json"] or "[]")),
                revision=int(row["revision"]),
            )
            for row in rows
        ]

    def list_wiki_sections(self, project_id: int) -> list[WikiSection]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM wiki_sections
                WHERE project_id = ?
                ORDER BY page_slug ASC, ordinal ASC
                """,
                (project_id,),
            ).fetchall()
        return [_row_to_section(row) for row in rows]

    def list_wiki_links(self, project_id: int) -> list[WikiLink]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM wiki_links
                WHERE project_id = ?
                ORDER BY source_page_slug ASC, target_page_slug ASC
                """,
                (project_id,),
            ).fetchall()
        return [
            WikiLink(
                id=int(row["id"]),
                project_id=int(row["project_id"]),
                source_page_slug=str(row["source_page_slug"]),
                target_page_slug=str(row["target_page_slug"]),
                link_text=str(row["link_text"]),
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


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _json_list(value: Any) -> str:
    items = value if isinstance(value, list) else []
    return json.dumps([str(item) for item in items], ensure_ascii=False)


def _sections_for_page(page: dict[str, Any], default_citations: list[str]) -> list[dict[str, Any]]:
    sections = page.get("sections")
    if isinstance(sections, list) and sections:
        return [section for section in sections if isinstance(section, dict)]
    return [
        {
            "heading": _str(page.get("title")),
            "body_markdown": _str(page.get("body_markdown")),
            "citations": default_citations,
            "links": _extract_wikilinks(_str(page.get("body_markdown"))),
        }
    ]


def _extract_wikilinks(markdown: str) -> list[str]:
    return sorted({match.strip() for match in re.findall(r"\[\[([^\]]+)\]\]", markdown) if match.strip()})


def _slug(value: Any) -> str:
    text = _str(value).lower()
    text = re.sub(r"\[\[|\]\]", "", text)
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", text)
    return text.strip("-") or "untitled"


def _row_to_section(row) -> WikiSection:
    return WikiSection(
        id=int(row["id"]),
        section_uid=str(row["section_uid"]),
        project_id=int(row["project_id"]),
        page_id=int(row["page_id"]),
        page_slug=str(row["page_slug"]),
        heading=str(row["heading"]),
        ordinal=int(row["ordinal"]),
        body_markdown=str(row["body_markdown"]),
        citations=json.loads(str(row["citations_json"] or "[]")),
        source_chunk_uids=json.loads(str(row["source_chunk_uids_json"] or "[]")),
        source_citation_labels=json.loads(str(row["source_citation_labels_json"] or "[]")),
        links=json.loads(str(row["links_json"] or "[]")),
    )
