from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.ingestion.service import IngestionService
from domain_atlas.providers.vector_index import RetrievedWikiSection
from domain_atlas.web.app import create_app
from domain_atlas.workflow.autopilot import AutopilotWorkflow


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "guided_reliability_travel_agent.json"


@pytest.mark.e2e
def test_guided_flow_replays_blocked_candidates_then_builds_and_answers(tmp_path):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    settings = Settings(data_dir=tmp_path, INTAKE_LLM_ASSESSMENT_ENABLED=False)
    vector_index = RecordedVectorIndex()
    embedding_provider = RecordedEmbeddingProvider()
    ingestion = IngestionService(
        database_path=settings.database_path,
        data_dir=settings.data_dir,
        embedding_provider=embedding_provider,
        vector_index=vector_index,
        http_client=httpx.Client(transport=httpx.MockTransport(_response_handler(fixture))),
    )
    workflow = AutopilotWorkflow(
        database_path=settings.database_path,
        discovery_provider=RecordedDiscoveryProvider(fixture),
        ingestion_runner=ingestion,
        build_runner=RecordedBuildRunner(settings.database_path),
    )
    app = create_app(
        settings,
        chat_provider=RecordedQAChatProvider(),
        embedding_provider=embedding_provider,
        vector_index=vector_index,
        autopilot_runner=workflow,
    )
    client = TestClient(app)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(name="agent", scope="旅行代理", interaction_mode="guided")
    )

    response = client.post(f"/domains/{project.id}/autopilot", follow_redirects=False)

    assert response.status_code == 303
    _wait_for_workflow(settings.database_path, project.id)
    run = WorkflowRepository(settings.database_path).list_for_project(project.id)[0]
    ingestion_step = next(
        step
        for step in reversed(run.steps)
        if step.step_name == "ingest_sources" and step.status == "completed"
    )
    assert run.status == "completed"
    assert ingestion_step.output["terminal_reason"] == "minimum_sources_reached"
    assert ingestion_step.output["success_count"] == 2
    assert ingestion_step.output["attempted_count"] == 4
    assert [item["outcome"] for item in ingestion_step.output["attempted_sources"]] == [
        "failed",
        "failed",
        "ingested",
        "ingested",
    ]
    assert [item["error_category"] for item in ingestion_step.output["attempted_sources"][:2]] == [
        "access_denied",
        "access_denied",
    ]
    assert len([source for source in SourceRepository(settings.database_path).list_for_project(project.id) if source.status == "ingested"]) == 2

    dashboard = client.get(f"/domains/{project.id}")
    wiki = client.get(f"/domains/{project.id}/wiki")
    qa = client.post(
        f"/domains/{project.id}/qa",
        data={"question": "旅行代理如何帮助旅客？"},
        follow_redirects=False,
    )

    assert "已成功 2 / 至少 2 份资料" in dashboard.text
    assert "资料门槛已满足" in dashboard.text
    assert "旅行代理" in wiki.text
    assert qa.status_code == 303
    assert "旅行代理通过需求澄清、预订协调和售后支持帮助旅客。" in client.get(
        f"/domains/{project.id}/qa"
    ).text


def _response_handler(fixture: dict):
    responses = fixture["responses"]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses[str(request.url)]
        return httpx.Response(
            response["status_code"],
            headers={"content-type": "text/html; charset=utf-8"},
            text=response["body"],
        )

    return handler


def _wait_for_workflow(database_path: Path, project_id: int) -> None:
    repository = WorkflowRepository(database_path)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        runs = repository.list_for_project(project_id)
        if runs and not any(run.status in {"queued", "running"} for run in runs):
            return
        time.sleep(0.02)
    raise AssertionError("guided workflow did not finish in time")


class RecordedDiscoveryProvider:
    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture

    def search(self, query: str, limit: int):
        assert query == self.fixture["query"]
        assert limit == 12
        from domain_atlas.domain.source_candidates import SourceCandidateDraft

        return [SourceCandidateDraft(**item) for item in self.fixture["candidates"]]


class RecordedEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(len(text))] for text in texts]


class RecordedVectorIndex:
    def upsert_chunks(self, *, project_id: int, chunks, embeddings) -> None:
        return None

    def upsert_wiki_sections(self, *, project_id: int, sections, embeddings) -> None:
        return None

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return []

    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedWikiSection(
                section_uid="travel-agency#1",
                page_slug="travel-agency",
                heading="旅行代理服务",
                body_markdown="旅行代理通过需求澄清、预订协调和售后支持帮助旅客。",
                citations=["W:travel-agency#1"],
                source_chunk_uids=["recorded:travel:1"],
                source_citation_labels=["S3-C1", "S4-C1"],
                distance=0.1,
                metadata={},
            )
        ]


class RecordedBuildRunner:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def run(self, project_id: int):
        sources = [
            source
            for source in SourceRepository(self.database_path).list_for_project(project_id)
            if source.status == "ingested"
        ]
        citations = [f"S{source.id}-C1" for source in sources]
        KnowledgeArtifactRepository(self.database_path).replace_project_artifacts(
            project_id,
            {
                "source_profiles": [
                    {
                        "source_id": source.id,
                        "summary": "旅行代理资料。",
                        "authority_note": "录制回归资料。",
                        "coverage_note": "覆盖服务流程。",
                        "citations": citations,
                    }
                    for source in sources
                ],
                "concepts": [
                    {
                        "name": "旅行代理",
                        "definition": "协助旅客完成产品比较、预订与售后服务的角色。",
                        "prerequisites": [],
                        "related": ["行程设计"],
                        "citations": citations,
                    }
                ],
                "concept_edges": [],
                "wiki_pages": [
                    {
                        "slug": "travel-agency",
                        "page_type": "synthesis",
                        "path": "wiki/synthesis/travel-agency",
                        "title": "旅行代理",
                        "topic_path": "旅行代理",
                        "summary": "旅行代理把旅客需求连接到供应商预订与售后支持。",
                        "body_markdown": "旅行代理通过需求澄清、预订协调和售后支持帮助旅客。",
                        "citations": citations,
                        "sections": [
                            {
                                "section_uid": "travel-agency#1",
                                "heading": "旅行代理服务",
                                "body_markdown": "旅行代理通过需求澄清、预订协调和售后支持帮助旅客。",
                                "citations": ["W:travel-agency#1"],
                                "source_citation_labels": citations,
                                "source_chunk_uids": ["recorded:travel:1"],
                                "links": [],
                            }
                        ],
                    }
                ],
                "learning_guide": {},
                "learning_modules": [],
            },
        )
        DomainProjectRepository(self.database_path).update_build_status(project_id, "completed")


class RecordedQAChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "W:travel-agency#1" in user_prompt
        return {
            "answer": "旅行代理通过需求澄清、预订协调和售后支持帮助旅客。",
            "citations": ["W:travel-agency#1"],
            "evidence_status": "sufficient",
        }
