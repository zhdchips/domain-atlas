from __future__ import annotations

import sqlite3

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.wiki.lint import WikiLintService


def test_artifact_repository_persists_wiki_sections_and_links(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    repository = KnowledgeArtifactRepository(database_path)

    repository.replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [
                {
                    "slug": "agent",
                    "title": "Agent",
                    "topic_path": "核心概念/Agent",
                    "summary": "Agent 概念。",
                    "body_markdown": "Agent 和 [[Tool Use]] 相关。",
                    "citations": ["S1-C1"],
                    "sections": [
                        {
                            "section_uid": "agent#definition",
                            "heading": "定义",
                            "body_markdown": "Agent 和 [[Tool Use]] 相关。[S1-C1]",
                            "citations": ["W:agent#definition"],
                            "source_citation_labels": ["S1-C1"],
                            "source_chunk_uids": ["chunk:1"],
                            "links": ["Tool Use"],
                        }
                    ],
                },
                {
                    "slug": "tool-use",
                    "title": "Tool Use",
                    "topic_path": "核心概念/Tool Use",
                    "summary": "工具使用。",
                    "body_markdown": "工具使用让 Agent 连接外部能力。[S1-C1]",
                    "citations": ["S1-C1"],
                    "sections": [
                        {
                            "section_uid": "tool-use#definition",
                            "heading": "定义",
                            "body_markdown": "工具使用让 Agent 连接外部能力。[S1-C1]",
                            "citations": ["W:tool-use#definition"],
                            "source_citation_labels": ["S1-C1"],
                        }
                    ],
                },
            ],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [],
        },
    )

    pages = repository.list_wiki_pages(project.id)
    sections = repository.list_wiki_sections(project.id)
    links = repository.list_wiki_links(project.id)

    assert [page.slug for page in pages] == ["agent", "tool-use"]
    assert pages[0].page_type == "concept"
    assert pages[0].path == "wiki/concepts/agent"
    assert pages[0].updated_at
    assert sections[0].section_uid == "agent#definition"
    assert sections[0].source_citation_labels == ["S1-C1"]
    assert links[0].source_page_slug == "agent"
    assert links[0].target_page_slug == "tool-use"


def test_artifact_repository_persists_typed_workspace_paths(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Wiki"))
    repository = KnowledgeArtifactRepository(database_path)

    repository.replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [
                {
                    "slug": "index",
                    "page_type": "index",
                    "path": "wiki/index",
                    "title": "Wiki Index",
                    "topic_path": "index",
                    "summary": "索引。",
                    "body_markdown": "# Wiki Index",
                },
                {
                    "slug": "source-doc",
                    "page_type": "source",
                    "path": "wiki/sources/source-doc",
                    "title": "Source Doc",
                    "topic_path": "sources/Source Doc",
                    "summary": "来源摘要。",
                    "body_markdown": "来源摘要。",
                },
            ],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [],
        },
    )

    groups = repository.list_wiki_page_groups(project.id)
    source_page = repository.get_wiki_page_by_path(project.id, "wiki/sources/source-doc")

    assert groups["index"][0].path == "wiki/index"
    assert groups["source"][0].page_type == "source"
    assert source_page is not None
    assert source_page.title == "Source Doc"


def test_artifact_repository_persists_learning_guide(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Learning Guide"))
    repository = KnowledgeArtifactRepository(database_path)

    repository.replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_guide": {
                "summary": "领域速览。",
                "question_answers": [
                    {"question": "是什么", "answer": "领域定义。", "citations": ["S1-C1"]}
                ],
                "mainline": [
                    {"title": "主线", "explanation": "先理解定义。", "citations": ["S1-C1"]}
                ],
                "core_concepts": [
                    {
                        "name": "核心概念",
                        "explanation": "领域基础。",
                        "depends_on": [],
                        "citations": ["S1-C1"],
                    }
                ],
                "branches": [
                    {
                        "name": "支线",
                        "description": "进阶方向。",
                        "when_to_study": "掌握主线之后。",
                        "citations": ["S1-C1"],
                    }
                ],
                "details": [
                    {
                        "title": "细节",
                        "description": "可实践的细节。",
                        "practice_or_example": "写一段总结。",
                        "citations": ["S1-C1"],
                    }
                ],
                "citations": ["S1-C1"],
            },
            "learning_modules": [],
        },
    )

    guide = repository.get_learning_guide(project.id)

    assert guide is not None
    assert guide.summary == "领域速览。"
    assert guide.question_answers[0]["question"] == "是什么"
    assert guide.core_concepts[0]["depends_on"] == []
    assert guide.citations == ["S1-C1"]


def test_artifact_repository_persists_lesson_module_fields(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Lesson Modules"))
    repository = KnowledgeArtifactRepository(database_path)

    repository.replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [
                {
                    "stage": 1,
                    "title": "入门认知",
                    "stage_overview": "先理解领域是什么。",
                    "core_explanation": "这是 Agent 生成的核心讲解。",
                    "knowledge_blocks": [
                        {"title": "知识块", "body": "可直接学习的内容。", "citations": ["S1-C1"]}
                    ],
                    "examples": [
                        {"title": "案例", "body": "一个例子。", "citations": ["S1-C1"]}
                    ],
                    "misconceptions": [
                        {"title": "误区", "correction": "修正说明。", "citations": ["S1-C1"]}
                    ],
                    "objectives": ["建立理解"],
                    "readings": ["旧阅读入口"],
                    "key_concepts": ["概念"],
                    "check_questions": ["检查问题？"],
                    "practice_task": "实践任务。",
                    "further_reading": [
                        {"title": "证据来源", "locator": "wiki/index", "citations": ["S1-C1"]}
                    ],
                    "citations": ["S1-C1"],
                }
            ],
        },
    )

    modules = repository.list_learning_modules(project.id)

    assert len(modules) == 1
    assert modules[0].stage_overview == "先理解领域是什么。"
    assert modules[0].core_explanation == "这是 Agent 生成的核心讲解。"
    assert modules[0].knowledge_blocks[0]["title"] == "知识块"
    assert modules[0].examples[0]["title"] == "案例"
    assert modules[0].misconceptions[0]["correction"] == "修正说明。"
    assert modules[0].further_reading[0]["locator"] == "wiki/index"


def test_wiki_section_uids_are_project_scoped_and_deduplicated(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project_repository = DomainProjectRepository(database_path)
    first = project_repository.create(CreateDomainProject(name="First"))
    second = project_repository.create(CreateDomainProject(name="Second"))
    repository = KnowledgeArtifactRepository(database_path)

    payload = {
        "wiki_pages": [
            {
                "slug": "index",
                "page_type": "index",
                "path": "wiki/index",
                "title": "Wiki Index",
                "topic_path": "index",
                "summary": "索引。",
                "body_markdown": "# Wiki Index",
                "sections": [
                    {
                        "section_uid": "index#1",
                        "heading": "Index",
                        "body_markdown": "第一段。",
                    },
                    {
                        "section_uid": "index#1",
                        "heading": "Index Duplicate",
                        "body_markdown": "第二段。",
                    },
                ],
            }
        ],
        "source_profiles": [],
        "concepts": [],
        "concept_edges": [],
        "learning_modules": [],
    }

    repository.replace_project_artifacts(first.id, payload)
    repository.replace_project_artifacts(second.id, payload)

    first_sections = repository.list_wiki_sections(first.id)
    second_sections = repository.list_wiki_sections(second.id)

    assert [section.section_uid for section in first_sections] == ["index#1", "index#1-2"]
    assert [section.section_uid for section in second_sections] == ["index#1", "index#1-2"]


def test_wiki_page_workspace_columns_migrate_old_database(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE wiki_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                slug TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                topic_path TEXT NOT NULL,
                summary TEXT NOT NULL,
                body_markdown TEXT NOT NULL,
                citations_json TEXT NOT NULL DEFAULT '[]',
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO wiki_pages (
                project_id, slug, title, topic_path, summary, body_markdown, citations_json
            )
            VALUES (1, 'agent', 'Agent', 'Agent', 'summary', 'body', '[]')
            """
        )

    initialize_database(database_path)

    repository = KnowledgeArtifactRepository(database_path)
    page = repository.get_wiki_page_by_path(1, "wiki/concepts/agent")

    assert page is not None
    assert page.page_type == "concept"
    assert page.updated_at


def test_learning_guides_table_is_created_for_existing_database(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE domain_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT 'beginner',
                language TEXT NOT NULL DEFAULT 'zh',
                status TEXT NOT NULL DEFAULT 'draft',
                build_status TEXT NOT NULL DEFAULT 'not_started',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "learning_guides" in tables


def test_learning_module_lesson_columns_migrate_old_database(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE learning_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                stage INTEGER NOT NULL,
                title TEXT NOT NULL,
                objectives_json TEXT NOT NULL DEFAULT '[]',
                readings_json TEXT NOT NULL DEFAULT '[]',
                key_concepts_json TEXT NOT NULL DEFAULT '[]',
                check_questions_json TEXT NOT NULL DEFAULT '[]',
                practice_task TEXT NOT NULL DEFAULT '',
                citations_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(learning_modules)").fetchall()
        }

    assert "stage_overview" in columns
    assert "core_explanation" in columns
    assert "knowledge_blocks_json" in columns
    assert "examples_json" in columns
    assert "misconceptions_json" in columns
    assert "further_reading_json" in columns


def test_wiki_sections_global_uid_constraint_migrates_to_project_scope(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE wiki_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_uid TEXT NOT NULL UNIQUE,
                project_id INTEGER NOT NULL,
                page_id INTEGER NOT NULL,
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

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        indexes = connection.execute("PRAGMA index_list(wiki_sections)").fetchall()
        index_columns = {
            row[1]: [
                column[2]
                for column in connection.execute(f"PRAGMA index_info({row[1]})").fetchall()
            ]
            for row in indexes
        }

    assert index_columns["idx_wiki_sections_project_uid"] == ["project_id", "section_uid"]
    assert ["section_uid"] not in index_columns.values()


def test_wiki_lint_detects_missing_citations_orphans_and_duplicate_slugs(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    repository = KnowledgeArtifactRepository(database_path)

    repository.replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [
                {
                    "slug": "agent",
                    "title": "Agent",
                    "topic_path": "核心概念/Agent",
                    "summary": "Agent 概念。",
                    "body_markdown": "Agent。",
                    "sections": [
                        {
                            "section_uid": "agent#1",
                            "heading": "定义",
                            "body_markdown": "Agent 无引用。",
                        }
                    ],
                },
                {
                    "slug": "agent",
                    "title": "Agent Duplicate",
                    "topic_path": "核心概念/Agent",
                    "summary": "重复。",
                    "body_markdown": "重复。",
                    "sections": [
                        {
                            "section_uid": "agent-duplicate#1",
                            "heading": "定义",
                            "body_markdown": "重复。",
                            "citations": ["S1-C1"],
                        }
                    ],
                },
            ],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [],
        },
    )

    issues = WikiLintService(database_path).lint_project(project.id)
    codes = {issue.code for issue in issues}

    assert "wiki.section.missing_citation" in codes
    assert "wiki.page.duplicate_slug" in codes
    assert "wiki.page.duplicate_topic_path" in codes
