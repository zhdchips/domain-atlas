from __future__ import annotations

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
            text="<html><head><title>Agent Docs</title></head><body><h1>Agents</h1><p>Use tools.</p></body></html>",
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
    assert "Agents Use tools" in chunks[0].text
