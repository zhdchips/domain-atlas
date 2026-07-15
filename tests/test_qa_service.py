from __future__ import annotations

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.providers.vector_index import RetrievedChunk, RetrievedWikiSection
from domain_atlas.qa.service import INSUFFICIENT_MESSAGE, RetrievalQAService


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class EmptyVectorIndex:
    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return []

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return []


class HitVectorIndex:
    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return []

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedChunk(
                chunk_uid="chunk:1",
                text="Agents plan and use tools.",
                citation_label="S1-C1",
                source_id=1,
                distance=0.1,
                metadata={},
            )
        ]


class WikiHitVectorIndex:
    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedWikiSection(
                section_uid="agent#1",
                page_slug="agent",
                heading="Agent",
                body_markdown="Agent 会规划并使用工具完成任务。",
                citations=["W:agent#1"],
                source_chunk_uids=["chunk:1"],
                source_citation_labels=["S1-C1"],
                distance=0.1,
                metadata={},
            )
        ]

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        raise AssertionError("QA should query Wiki sections before source chunks.")


class AnswerChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "S1-C1" in user_prompt
        return {
            "answer": "Agent 会规划并使用工具完成任务。",
            "citations": ["S1-C1"],
            "evidence_status": "sufficient",
        }


class WikiAnswerChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "W:agent#1" in user_prompt
        return {
            "answer": "Agent 会规划并使用工具完成任务。",
            "citations": ["W:agent#1"],
            "evidence_status": "sufficient",
        }


def test_qa_service_records_insufficient_answer_when_no_chunks(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    service = RetrievalQAService(
        database_path=database_path,
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=EmptyVectorIndex(),
        chat_provider=AnswerChatProvider(),
    )

    record = service.answer(project_id=project.id, question="什么是 Agent？")

    assert record.answer == INSUFFICIENT_MESSAGE
    assert record.citations == []
    assert record.evidence_status == "insufficient"


def test_qa_service_records_cited_answer(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    service = RetrievalQAService(
        database_path=database_path,
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=HitVectorIndex(),
        chat_provider=AnswerChatProvider(),
    )

    record = service.answer(project_id=project.id, question="什么是 Agent？")

    assert record.answer == "Agent 会规划并使用工具完成任务。"
    assert record.citations == ["S1-C1"]
    assert record.source_provenance == ["S1-C1"]
    assert record.evidence_status == "sufficient"


def test_qa_service_prefers_wiki_sections_over_source_chunks(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    service = RetrievalQAService(
        database_path=database_path,
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=WikiHitVectorIndex(),
        chat_provider=WikiAnswerChatProvider(),
    )

    record = service.answer(project_id=project.id, question="什么是 Agent？")

    assert record.answer == "Agent 会规划并使用工具完成任务。"
    assert record.citations == ["W:agent#1"]
    assert record.source_provenance == ["S1-C1"]
    assert record.evidence_status == "sufficient"
