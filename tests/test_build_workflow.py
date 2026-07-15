from __future__ import annotations

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import ChunkRepository, CreateChunk, CreateSource, SourceRepository
from domain_atlas.workflow.build import KnowledgeBuildWorkflow


class FakeChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "encyclopedia-style" in system_prompt
        assert "S1-C1" in user_prompt
        return build_payload()


def build_payload():
    return {
        "source_profiles": [
            {
                "source_id": 1,
                "summary": "资料介绍了 Agent 的工具使用。",
                "authority_note": "测试资料。",
                "coverage_note": "覆盖基础概念。",
                "citations": ["S1-C1"],
            }
        ],
        "concepts": [
            {
                "name": "Agent",
                "definition": "能够规划并使用工具完成任务的系统。",
                "prerequisites": [],
                "related": ["Tool Use"],
                "citations": ["S1-C1"],
            }
        ],
        "concept_edges": [
            {
                "source": "Agent",
                "target": "Tool Use",
                "relation": "related",
                "citations": ["S1-C1"],
            }
        ],
        "wiki_pages": [
            {
                "title": "Agent",
                "topic_path": "核心概念/Agent",
                "summary": "Agent 是能够规划并使用工具的系统。",
                "body_markdown": "## 定义\nAgent 能够规划并使用工具。[S1-C1]",
                "citations": ["S1-C1"],
            }
        ],
        "learning_modules": [
            {
                "stage": stage,
                "title": title,
                "objectives": [f"理解{title}"],
                "readings": ["Agent [S1-C1]"],
                "key_concepts": ["Agent"],
                "check_questions": ["Agent 为什么需要工具？"],
                "practice_task": "用一句话解释 Agent。",
                "citations": ["S1-C1"],
            }
            for stage, title in enumerate(
                ["入门认知", "核心概念", "关键方法", "实践应用", "进阶专题"],
                start=1,
            )
        ],
    }


def test_knowledge_build_workflow_persists_artifacts(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="markdown",
            title="Agent Source",
            locator="fixture",
        )
    )
    ChunkRepository(database_path).replace_for_source(
        source.id,
        [
            CreateChunk(
                chunk_uid="chunk:1",
                project_id=project.id,
                source_id=source.id,
                ordinal=1,
                text="Agents plan and use tools.",
                citation_label="S1-C1",
                metadata={"source_title": "Agent Source"},
            )
        ],
    )

    workflow = KnowledgeBuildWorkflow(database_path=database_path, chat_provider=FakeChatProvider())
    workflow.run(project.id)

    repository = KnowledgeArtifactRepository(database_path)
    pages = repository.list_wiki_pages(project.id)
    modules = repository.list_learning_modules(project.id)
    updated_project = DomainProjectRepository(database_path).get(project.id)
    paths = {page.path: page for page in pages}

    assert paths["wiki/index"].title == "Wiki Index"
    assert paths["wiki/log"].page_type == "log"
    assert paths["wiki/templates/source"].page_type == "template"
    assert paths["wiki/templates/concept"].page_type == "template"
    assert any(page.page_type == "source" for page in pages)
    assert any(page.path == "wiki/concepts/agent" for page in pages)
    assert paths["wiki/synthesis/overview"].page_type == "synthesis"
    agent_page = paths["wiki/concepts/agent"]
    assert agent_page.title == "Agent"
    assert agent_page.citations == ["S1-C1"]
    assert len(modules) == 5
    assert modules[0].title == "入门认知"
    assert updated_project is not None
    assert updated_project.build_status == "completed"
