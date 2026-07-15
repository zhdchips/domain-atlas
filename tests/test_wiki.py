from __future__ import annotations

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
    assert sections[0].section_uid == "agent#definition"
    assert sections[0].source_citation_labels == ["S1-C1"]
    assert links[0].source_page_slug == "agent"
    assert links[0].target_page_slug == "tool-use"


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
