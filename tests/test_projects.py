from __future__ import annotations

import sqlite3

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository


def test_initialize_database_creates_domain_projects_table(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'domain_projects'
            """
        ).fetchone()

    assert table is not None


def test_project_repository_creates_lists_and_gets_project(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    repository = DomainProjectRepository(database_path)

    created = repository.create(
        CreateDomainProject(
            name="  强化学习  ",
            goal="理解核心算法",
            level="beginner",
            language="zh",
        )
    )

    assert created.id > 0
    assert created.name == "强化学习"
    assert created.goal == "理解核心算法"
    assert created.language == "zh"
    assert created.interaction_mode == "guided"
    assert created.scope == ""
    assert created.intake_status == "confirmed"
    assert created.intake_metadata == {}
    assert created.status == "draft"
    assert created.build_status == "not_started"
    assert repository.get(created.id) == created
    assert repository.list_recent() == [created]


def test_project_repository_rejects_blank_name(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    repository = DomainProjectRepository(database_path)

    try:
        repository.create(CreateDomainProject(name="  "))
    except ValueError as exc:
        assert "name is required" in str(exc)
    else:
        raise AssertionError("Expected blank project name to be rejected.")


def test_project_repository_persists_expert_interaction_mode(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    repository = DomainProjectRepository(database_path)

    created = repository.create(
        CreateDomainProject(
            name="LLM Agents",
            interaction_mode="expert",
        )
    )

    assert created.interaction_mode == "expert"
    assert repository.get(created.id).interaction_mode == "expert"


def test_initialize_database_migrates_existing_projects_to_confirmed_intake(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE domain_projects (
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
            INSERT INTO domain_projects (name) VALUES ('旧项目');
            """
        )

    initialize_database(database_path)

    project = DomainProjectRepository(database_path).get(1)
    assert project is not None
    assert project.scope == ""
    assert project.intake_status == "confirmed"
    assert project.intake_metadata == {}
