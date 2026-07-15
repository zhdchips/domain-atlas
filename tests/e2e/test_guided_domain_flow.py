from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.sources import ChunkRepository, CreateChunk, CreateSource, SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.providers.vector_index import RetrievedChunk, RetrievedWikiSection
from domain_atlas.web.app import create_app


@pytest.mark.e2e
def test_guided_domain_flow_navigation_and_qa_are_deterministic(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    autopilot = DeterministicAutopilotRunner(database_path=database_path, data_dir=tmp_path)
    app = create_app(
        Settings(data_dir=tmp_path),
        chat_provider=DeterministicQAChatProvider(),
        embedding_provider=DeterministicEmbeddingProvider(),
        vector_index=DeterministicVectorIndex(),
        autopilot_runner=autopilot,
    )
    client = TestClient(app)

    create = client.post(
        "/domains",
        data={
            "name": "Dataphin",
            "goal": "入门",
            "level": "beginner",
            "language": "zh",
            "interaction_mode": "guided",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303
    assert create.headers["location"] == "/domains/1"

    autopilot_response = client.post("/domains/1/autopilot", follow_redirects=False)
    assert autopilot_response.status_code == 303
    assert autopilot_response.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert dashboard.status_code == 200
    assert "completed" in dashboard.text
    assert "Chunks" in dashboard.text
    assert "Wiki" in dashboard.text
    assert 'href="/domains/1#sources"' in dashboard.text
    assert 'href="/domains/1/wiki"' in dashboard.text
    assert 'href="/domains/1/path"' in dashboard.text
    assert 'href="/domains/1/qa"' in dashboard.text

    wiki = client.get("/domains/1/wiki")
    assert wiki.status_code == 200
    assert "LLM Wiki Workspace" in wiki.text
    assert "wiki/index" in wiki.text
    assert "wiki/log" in wiki.text
    assert "sources" in wiki.text
    assert "concepts" in wiki.text
    assert "entities" in wiki.text
    assert "synthesis" in wiki.text
    assert "templates" in wiki.text
    assert "queries" in wiki.text
    assert "Dataphin 入门" in wiki.text
    assert "Central catalog" in wiki.text

    concept_page = client.get("/domains/1/wiki/wiki/concepts/dataphin")
    assert concept_page.status_code == 200
    assert "Dataphin 是一体化数据建设与治理平台" in concept_page.text

    learning_path = client.get("/domains/1/path")
    assert learning_path.status_code == 200
    assert "入门认知" in learning_path.text
    assert "画出 Dataphin 的核心对象关系" in learning_path.text

    qa_page = client.get("/domains/1/qa")
    assert qa_page.status_code == 200
    assert "还没有问答记录" in qa_page.text

    ask = client.post(
        "/domains/1/qa",
        data={"question": "Dataphin 是什么？"},
        follow_redirects=False,
    )
    assert ask.status_code == 303
    assert ask.headers["location"] == "/domains/1/qa"

    qa_result = client.get("/domains/1/qa")
    assert qa_result.status_code == 200
    assert "Dataphin 是一体化数据建设与治理平台。" in qa_result.text
    assert "W:dataphin#1" in qa_result.text
    assert "S1-C1" in qa_result.text


class DeterministicAutopilotRunner:
    def __init__(self, *, database_path: Path, data_dir: Path) -> None:
        self.database_path = database_path
        self.data_dir = data_dir

    def run(self, project_id: int):
        project_repository = DomainProjectRepository(self.database_path)
        source_repository = SourceRepository(self.database_path)
        chunk_repository = ChunkRepository(self.database_path)
        artifact_repository = KnowledgeArtifactRepository(self.database_path)
        workflow_repository = WorkflowRepository(self.database_path)

        source = source_repository.create(
            CreateSource(
                project_id=project_id,
                source_type="url",
                title="Dataphin Docs",
                locator="https://docs.example.test/dataphin",
                metadata={"auto_accepted": True},
            )
        )
        raw_path = self.data_dir / "fixtures" / "dataphin.html"
        normalized_path = self.data_dir / "fixtures" / "dataphin.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("<html>Dataphin docs</html>", encoding="utf-8")
        normalized_path.write_text(
            "Dataphin 是一体化数据建设与治理平台。", encoding="utf-8"
        )
        source_repository.update_ingested(
            source.id,
            raw_path=str(raw_path),
            normalized_path=str(normalized_path),
            checksum="deterministic",
            metadata={
                **source.metadata,
                "title": "Dataphin Docs",
                "content_type": "text/html",
                "chunk_count": 1,
            },
        )
        chunk_repository.replace_for_source(
            source.id,
            [
                CreateChunk(
                    chunk_uid="chunk:dataphin:1",
                    project_id=project_id,
                    source_id=source.id,
                    ordinal=1,
                    text="Dataphin 是一体化数据建设与治理平台。",
                    citation_label="S1-C1",
                    metadata={
                        "source_title": "Dataphin Docs",
                        "source_type": "url",
                        "locator": "https://docs.example.test/dataphin",
                    },
                )
            ],
        )
        artifact_repository.replace_project_artifacts(project_id, _artifact_payload(source.id))

        guided_run_id = workflow_repository.start_run(project_id, "guided_autopilot")
        workflow_repository.record_step(
            guided_run_id,
            step_name="discover_candidates",
            status="completed",
            output={"candidate_count": 1},
        )
        workflow_repository.record_step(
            guided_run_id,
            step_name="ingest_sources",
            status="completed",
            output={"source_ids": [source.id], "failed_sources": []},
        )
        workflow_repository.record_step(
            guided_run_id,
            step_name="build_knowledge",
            status="completed",
            output={"status": "completed"},
        )
        workflow_repository.finish_run(guided_run_id)

        build_run_id = workflow_repository.start_run(project_id, "knowledge_build")
        workflow_repository.record_step(
            build_run_id,
            step_name="persist_artifacts",
            status="completed",
            output={"wiki_sections": 1},
        )
        workflow_repository.finish_run(build_run_id)
        project_repository.update_build_status(project_id, "completed")


class DeterministicEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(len(text))] for text in texts]


class DeterministicVectorIndex:
    def upsert_chunks(self, *, project_id: int, chunks, embeddings) -> None:
        return None

    def upsert_wiki_sections(self, *, project_id: int, sections, embeddings) -> None:
        return None

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedChunk(
                chunk_uid="chunk:dataphin:1",
                text="Dataphin 是一体化数据建设与治理平台。",
                citation_label="S1-C1",
                source_id=1,
                distance=0.1,
                metadata={},
            )
        ]

    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedWikiSection(
                section_uid="dataphin#1",
                page_slug="dataphin",
                heading="Dataphin 入门",
                body_markdown="Dataphin 是一体化数据建设与治理平台。",
                citations=["W:dataphin#1"],
                source_chunk_uids=["chunk:dataphin:1"],
                source_citation_labels=["S1-C1"],
                distance=0.1,
                metadata={},
            )
        ]


class DeterministicQAChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "W:dataphin#1" in user_prompt
        return {
            "answer": "Dataphin 是一体化数据建设与治理平台。",
            "citations": ["W:dataphin#1"],
            "evidence_status": "sufficient",
        }


def _artifact_payload(source_id: int) -> dict:
    return {
        "source_profiles": [
            {
                "source_id": source_id,
                "summary": "Dataphin 文档。",
                "authority_note": "确定性测试资料。",
                "coverage_note": "覆盖入门定义。",
                "citations": ["S1-C1"],
            }
        ],
        "concepts": [
            {
                "name": "Dataphin",
                "definition": "一体化数据建设与治理平台。",
                "prerequisites": [],
                "related": ["数据治理"],
                "citations": ["S1-C1"],
            }
        ],
        "concept_edges": [
            {
                "source": "Dataphin",
                "target": "数据治理",
                "relation": "supports",
                "citations": ["S1-C1"],
            }
        ],
        "wiki_pages": [
            {
                "title": "Wiki Index",
                "slug": "index",
                "page_type": "index",
                "path": "wiki/index",
                "topic_path": "index",
                "summary": "Central catalog of the Wiki workspace.",
                "body_markdown": "# Wiki Index\n\n- [[Dataphin 入门]] — Dataphin 是一体化数据建设与治理平台。",
                "citations": [],
            },
            {
                "title": "Wiki Log",
                "slug": "log",
                "page_type": "log",
                "path": "wiki/log",
                "topic_path": "log",
                "summary": "Chronological build log.",
                "body_markdown": "# Wiki Log\n\n## build\n- Sources: 1\n- Chunks: 1",
                "citations": [],
            },
            {
                "title": "Dataphin Docs",
                "slug": "source-1-dataphin-docs",
                "page_type": "source",
                "path": "wiki/sources/source-1-dataphin-docs",
                "topic_path": "sources/Dataphin Docs",
                "summary": "Dataphin 文档。",
                "body_markdown": "# Dataphin Docs\n\nDataphin 文档。",
                "citations": ["S1-C1"],
            },
            {
                "title": "Dataphin 入门",
                "slug": "dataphin",
                "page_type": "concept",
                "path": "wiki/concepts/dataphin",
                "topic_path": "Dataphin/入门",
                "summary": "Dataphin 是一体化数据建设与治理平台。",
                "body_markdown": "# Dataphin 入门\n\nDataphin 是一体化数据建设与治理平台。[S1-C1]",
                "citations": ["S1-C1"],
                "sections": [
                    {
                        "section_uid": "dataphin#1",
                        "heading": "Dataphin 入门",
                        "body_markdown": "Dataphin 是一体化数据建设与治理平台。",
                        "citations": ["W:dataphin#1"],
                        "source_citation_labels": ["S1-C1"],
                        "source_chunk_uids": ["chunk:dataphin:1"],
                        "links": [],
                    }
                ],
            },
            {
                "title": "Dataphin synthesis",
                "slug": "overview",
                "page_type": "synthesis",
                "path": "wiki/synthesis/overview",
                "topic_path": "synthesis/overview",
                "summary": "跨页面综合总结。",
                "body_markdown": "# Dataphin synthesis\n\nDataphin 连接数据建设与治理。",
                "citations": ["S1-C1"],
            },
            {
                "title": "Source page template",
                "slug": "source-template",
                "page_type": "template",
                "path": "wiki/templates/source",
                "topic_path": "templates/source",
                "summary": "Template for source pages.",
                "body_markdown": "# Source page template",
                "citations": [],
            },
            {
                "title": "Concept page template",
                "slug": "concept-template",
                "page_type": "template",
                "path": "wiki/templates/concept",
                "topic_path": "templates/concept",
                "summary": "Template for concept pages.",
                "body_markdown": "# Concept page template",
                "citations": [],
            },
        ],
        "learning_modules": [
            {
                "stage": stage,
                "title": title,
                "objectives": ["理解 Dataphin 的基本定位"],
                "readings": ["Dataphin 入门 [S1-C1]"],
                "key_concepts": ["Dataphin"],
                "check_questions": ["Dataphin 是什么？"],
                "practice_task": "画出 Dataphin 的核心对象关系。",
                "citations": ["S1-C1"],
            }
            for stage, title in enumerate(
                ["入门认知", "核心概念", "关键方法", "实践应用", "进阶专题"],
                start=1,
            )
        ],
    }
