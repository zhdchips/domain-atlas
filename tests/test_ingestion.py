from __future__ import annotations

from pathlib import Path

import httpx

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import (
    ChunkRepository,
    CreateSource,
    SourceRepository,
)
from domain_atlas.ingestion.service import IngestionService


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), float(len(text))] for index, text in enumerate(texts, start=1)]


class FakeVectorIndex:
    def __init__(self) -> None:
        self.calls = []

    def upsert_chunks(self, *, project_id: int, chunks, embeddings) -> None:
        self.calls.append(
            {
                "project_id": project_id,
                "chunk_count": len(chunks),
                "embedding_count": len(embeddings),
                "citation_labels": [chunk.citation_label for chunk in chunks],
            }
        )


def test_markdown_ingestion_writes_artifacts_chunks_and_vectors(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    raw_path = tmp_path / "agent.md"
    raw_path.write_text("# Agents\n\nAgents plan, use tools, and verify outcomes.", encoding="utf-8")
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="markdown",
            title="Agents",
            locator="upload:agent.md",
            raw_path=str(raw_path),
        )
    )
    vector_index = FakeVectorIndex()
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
    )

    updated, chunks = service.ingest_source(source.id)

    assert updated.status == "ingested"
    assert updated.checksum
    assert updated.normalized_path.endswith("normalized.txt")
    assert updated.metadata["chunk_count"] == len(chunks)
    assert chunks[0].citation_label == f"S{source.id}-C1"
    assert "Agents plan" in chunks[0].text
    assert ChunkRepository(database_path).list_for_source(source.id) == chunks
    assert vector_index.calls == [
        {
            "project_id": project.id,
            "chunk_count": len(chunks),
            "embedding_count": len(chunks),
            "citation_labels": [chunk.citation_label for chunk in chunks],
        }
    ]


def test_url_ingestion_uses_mock_http_client(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><head><title>Agent Docs</title></head><body><h1>Agents</h1>"
                "<p>Agents plan tasks, call tools, inspect evidence, and verify each outcome. "
                "This documentation explains the lifecycle, constraints, and recovery behavior "
                "for a reliable agent workflow.</p></body></html>"
            ),
        )

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="url",
            title="Agent Docs",
            locator="https://docs.example.com/agents",
        )
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    updated, chunks = service.ingest_source(source.id)

    assert updated.status == "ingested"
    assert updated.metadata["title"] == "Agent Docs"
    assert "Agents plan tasks" in chunks[0].text


def test_url_ingestion_retries_read_failure_without_duplicate_records(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><head><title>Agent Docs</title></head><body><p>"
                "Use tools with explicit plans, inspect returned evidence, and verify every "
                "result before continuing. This page documents a complete agent workflow, "
                "including its lifecycle, constraints, recovery behavior, and evidence checks."
                "</p></body></html>"
            ),
        )

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source_repository = SourceRepository(database_path)
    source = source_repository.create(
        CreateSource(
            project_id=project.id,
            source_type="url",
            title="Agent Docs",
            locator="https://docs.example.com/agents",
        )
    )
    vector_index = FakeVectorIndex()
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        url_fetch_max_retries=1,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
    )

    updated, first_chunks = service.ingest_source(source.id)
    _, second_chunks = service.ingest_source(source.id)

    assert updated.status == "ingested"
    assert calls["count"] == 3
    assert len(source_repository.list_for_project(project.id)) == 1
    assert ChunkRepository(database_path).list_for_source(source.id) == second_chunks
    assert len(first_chunks) == len(second_chunks) == 1
    assert len(vector_index.calls) == 2


def test_url_ingestion_excludes_navigation_only_html_and_keeps_artifacts(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><head><title>Template</title></head><body><nav>Sign in Navigation Menu "
                "Footer Navigation Cookie Settings</nav><footer>All rights reserved</footer></body></html>"
            ),
        )

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source_repository = SourceRepository(database_path)
    source = source_repository.create(
        CreateSource(project_id=project.id, source_type="url", title="Template", locator="https://example.com")
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        service.ingest_source(source.id)
    except ValueError as exc:
        assert "content quality" in str(exc)
    else:
        raise AssertionError("Expected navigation-only page to be excluded.")

    excluded = source_repository.get(source.id)
    assert excluded is not None
    assert excluded.status == "excluded"
    assert excluded.metadata["content_quality"]["accepted"] is False
    assert Path(excluded.raw_path).exists()
    assert Path(excluded.normalized_path).exists()
    assert ChunkRepository(database_path).list_for_source(source.id) == []


def test_url_ingestion_ignores_navigation_chrome_when_main_content_is_present(tmp_path):
    main_text = (
        "Agent systems should separate plans, tool calls, evidence, verification, retries, and "
        "human review. This primary content explains how to inspect every operation, preserve "
        "citations, and recover from failures without allowing page templates to dominate the source."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><head><title>Agent Docs</title></head><body>"
                "<nav>Sign in Navigation Menu Footer Navigation Cookie Settings</nav>"
                f"<main><h1>Agents</h1><p>{main_text}</p></main>"
                "<footer>All rights reserved</footer></body></html>"
            ),
        )

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(project_id=project.id, source_type="url", title="Agent Docs", locator="https://example.com/docs")
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    _, chunks = service.ingest_source(source.id)

    assert main_text in chunks[0].text
    assert "Navigation Menu" not in chunks[0].text
    assert "All rights reserved" not in chunks[0].text


def test_url_ingestion_excludes_obvious_duplicate_before_chunks_are_written(tmp_path):
    body = (
        "<html><head><title>Agent Docs</title></head><body><main><h1>Agents</h1><p>"
        "Agents plan tasks, call tools, inspect evidence, and verify each outcome. "
        "This documentation explains the lifecycle, constraints, and recovery behavior "
        "for a reliable agent workflow with enough detail to be treated as source material."
        "</p></main></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body)

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source_repository = SourceRepository(database_path)
    first = source_repository.create(
        CreateSource(project_id=project.id, source_type="url", title="Agent Docs", locator="https://docs.example.com/a")
    )
    second = source_repository.create(
        CreateSource(project_id=project.id, source_type="url", title="Mirror", locator="https://mirror.example.com/a")
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    service.ingest_source(first.id)
    try:
        service.ingest_source(second.id)
    except ValueError as exc:
        assert "near-duplicate evidence" in str(exc)
    else:
        raise AssertionError("Expected duplicate source to be excluded.")

    assert source_repository.get(second.id).status == "excluded"
    assert ChunkRepository(database_path).list_for_source(second.id) == []
    assert len(ChunkRepository(database_path).list_for_source(first.id)) == 1


def test_url_ingestion_does_not_retry_access_error(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(403, text="secret provider response")

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="url",
            title="Agent Docs",
            locator="https://docs.example.com/agents",
        )
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        url_fetch_max_retries=2,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
    )

    try:
        service.ingest_source(source.id)
    except ValueError as exc:
        assert "配置或访问受限" in str(exc)
        assert "secret provider response" not in str(exc)
    else:
        raise AssertionError("Expected access failure.")
    assert calls["count"] == 1


def test_url_ingestion_exhausts_retryable_server_error_safely(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, text="secret provider response")

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="url",
            title="Agent Docs",
            locator="https://docs.example.com/agents",
        )
    )
    service = IngestionService(
        database_path=database_path,
        data_dir=tmp_path / "data",
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        url_fetch_max_retries=1,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
    )

    try:
        service.ingest_source(source.id)
    except ValueError as exc:
        assert "URL 资料抓取服务暂时不可用" in str(exc)
        assert "2/2" in str(exc)
        assert "secret provider response" not in str(exc)
    else:
        raise AssertionError("Expected retry exhaustion.")
    assert calls["count"] == 2
