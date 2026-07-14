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
