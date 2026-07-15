"""SQLite database helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS domain_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    goal TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'beginner',
    language TEXT NOT NULL DEFAULT 'zh',
    interaction_mode TEXT NOT NULL DEFAULT 'guided',
    status TEXT NOT NULL DEFAULT 'draft',
    build_status TEXT NOT NULL DEFAULT 'not_started',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domain_projects_updated_at
ON domain_projects(updated_at DESC);

CREATE TABLE IF NOT EXISTS source_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'web',
    publisher TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    authority_score REAL NOT NULL DEFAULT 0.0,
    authority_reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'discovered',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_candidates_project
ON source_candidates(project_id, status, authority_score DESC);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    locator TEXT NOT NULL,
    raw_path TEXT NOT NULL DEFAULT '',
    normalized_path TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sources_project
ON sources(project_id, status, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_project_locator
ON sources(project_id, locator);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_uid TEXT NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    citation_label TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_project
ON chunks(project_id, source_id, ordinal);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    output_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    authority_note TEXT NOT NULL DEFAULT '',
    coverage_note TEXT NOT NULL DEFAULT '',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    definition TEXT NOT NULL,
    prerequisites_json TEXT NOT NULL DEFAULT '[]',
    related_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS concept_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    source_concept TEXT NOT NULL,
    target_concept TEXT NOT NULL,
    relation TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wiki_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    slug TEXT NOT NULL DEFAULT '',
    page_type TEXT NOT NULL DEFAULT 'concept',
    path TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    topic_path TEXT NOT NULL,
    summary TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wiki_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_uid TEXT NOT NULL,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    page_id INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    page_slug TEXT NOT NULL,
    heading TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    body_markdown TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    source_chunk_uids_json TEXT NOT NULL DEFAULT '[]',
    source_citation_labels_json TEXT NOT NULL DEFAULT '[]',
    links_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wiki_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    source_page_slug TEXT NOT NULL,
    target_page_slug TEXT NOT NULL,
    link_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL UNIQUE REFERENCES domain_projects(id) ON DELETE CASCADE,
    summary TEXT NOT NULL DEFAULT '',
    question_answers_json TEXT NOT NULL DEFAULT '[]',
    mainline_json TEXT NOT NULL DEFAULT '[]',
    core_concepts_json TEXT NOT NULL DEFAULT '[]',
    branches_json TEXT NOT NULL DEFAULT '[]',
    details_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    stage INTEGER NOT NULL,
    title TEXT NOT NULL,
    objectives_json TEXT NOT NULL DEFAULT '[]',
    readings_json TEXT NOT NULL DEFAULT '[]',
    key_concepts_json TEXT NOT NULL DEFAULT '[]',
    check_questions_json TEXT NOT NULL DEFAULT '[]',
    practice_task TEXT NOT NULL DEFAULT '',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_project
ON wiki_pages(project_id, topic_path);

CREATE INDEX IF NOT EXISTS idx_wiki_sections_project
ON wiki_sections(project_id, page_slug, ordinal);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_sections_project_uid
ON wiki_sections(project_id, section_uid);

CREATE INDEX IF NOT EXISTS idx_wiki_links_project
ON wiki_links(project_id, source_page_slug, target_page_slug);

CREATE INDEX IF NOT EXISTS idx_learning_modules_project
ON learning_modules(project_id, stage);

CREATE INDEX IF NOT EXISTS idx_learning_guides_project
ON learning_guides(project_id);

CREATE TABLE IF NOT EXISTS qa_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    source_provenance_json TEXT NOT NULL DEFAULT '[]',
    evidence_status TEXT NOT NULL DEFAULT 'sufficient',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qa_records_project
ON qa_records(project_id, id DESC);
"""


def initialize_database(database_path: Path) -> None:
    """Create the SQLite database and required tables."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        _migrate_wiki_sections_project_scoped_uid(connection)
        _ensure_column(connection, "wiki_pages", "slug", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "wiki_pages", "page_type", "TEXT NOT NULL DEFAULT 'concept'")
        _ensure_column(connection, "wiki_pages", "path", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "wiki_pages", "revision", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(
            connection,
            "wiki_pages",
            "updated_at",
            "TEXT NOT NULL DEFAULT ''",
        )
        connection.execute(
            """
            UPDATE wiki_pages
            SET path = 'wiki/concepts/' || COALESCE(NULLIF(slug, ''), id)
            WHERE path = ''
            """
        )
        connection.execute(
            """
            UPDATE wiki_pages
            SET updated_at = created_at
            WHERE updated_at = ''
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wiki_pages_slug
            ON wiki_pages(project_id, slug)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wiki_pages_workspace
            ON wiki_pages(project_id, page_type, path)
            """
        )
        _ensure_column(
            connection,
            "domain_projects",
            "interaction_mode",
            "TEXT NOT NULL DEFAULT 'guided'",
        )
        _ensure_column(
            connection,
            "qa_records",
            "source_provenance_json",
            "TEXT NOT NULL DEFAULT '[]'",
        )


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with row dictionaries and foreign keys enabled."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _migrate_wiki_sections_project_scoped_uid(connection: sqlite3.Connection) -> None:
    """Replace old globally-unique section_uid schema with project-scoped uniqueness."""
    if not _has_global_wiki_section_uid_constraint(connection):
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_sections_project_uid
            ON wiki_sections(project_id, section_uid)
            """
        )
        return

    connection.execute("ALTER TABLE wiki_sections RENAME TO wiki_sections_old")
    connection.execute(
        """
        CREATE TABLE wiki_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_uid TEXT NOT NULL,
            project_id INTEGER NOT NULL REFERENCES domain_projects(id) ON DELETE CASCADE,
            page_id INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
            page_slug TEXT NOT NULL,
            heading TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            body_markdown TEXT NOT NULL,
            citations_json TEXT NOT NULL DEFAULT '[]',
            source_chunk_uids_json TEXT NOT NULL DEFAULT '[]',
            source_citation_labels_json TEXT NOT NULL DEFAULT '[]',
            links_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO wiki_sections (
            id,
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
            links_json,
            created_at
        )
        SELECT
            id,
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
            links_json,
            created_at
        FROM wiki_sections_old
        """
    )
    connection.execute("DROP TABLE wiki_sections_old")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wiki_sections_project
        ON wiki_sections(project_id, page_slug, ordinal)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_sections_project_uid
        ON wiki_sections(project_id, section_uid)
        """
    )


def _has_global_wiki_section_uid_constraint(connection: sqlite3.Connection) -> bool:
    indexes = connection.execute("PRAGMA index_list(wiki_sections)").fetchall()
    for index in indexes:
        if str(index["origin"]) != "u":
            continue
        columns = [
            str(row["name"])
            for row in connection.execute(f"PRAGMA index_info({index['name']})").fetchall()
        ]
        if columns == ["section_uid"]:
            return True
    return False
