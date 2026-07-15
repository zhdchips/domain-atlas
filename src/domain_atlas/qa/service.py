"""Citation-grounded retrieval QA service."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from domain_atlas.domain.qa import QARecord, QARepository
from domain_atlas.providers.vector_index import RetrievedChunk, RetrievedWikiSection, VectorIndex


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class ChatProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        ...


INSUFFICIENT_MESSAGE = "当前知识库信息不足，无法基于已摄取资料可靠回答。建议补充更权威或更直接相关的资料。"


class RetrievalQAService:
    def __init__(
        self,
        *,
        database_path: Path,
        embedding_provider: EmbeddingProvider,
        vector_index: VectorIndex,
        chat_provider: ChatProvider,
        top_k: int = 5,
    ) -> None:
        self.repository = QARepository(database_path)
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index
        self.chat_provider = chat_provider
        self.top_k = top_k

    def answer(self, *, project_id: int, question: str) -> QARecord:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question is required.")
        embedding = self.embedding_provider.embed_texts([clean_question])[0]
        wiki_sections = self.vector_index.query_wiki_sections(
            project_id=project_id,
            query_embedding=embedding,
            limit=self.top_k,
        )
        if wiki_sections:
            return self._answer_from_wiki(
                project_id=project_id,
                question=clean_question,
                retrieved=wiki_sections,
            )

        source_chunks = self.vector_index.query(
            project_id=project_id,
            query_embedding=embedding,
            limit=self.top_k,
        )
        if not source_chunks:
            return self.repository.create(
                project_id=project_id,
                question=clean_question,
                answer=INSUFFICIENT_MESSAGE,
                citations=[],
                source_provenance=[],
                evidence_status="insufficient",
            )

        payload = self.chat_provider.complete_json(
            system_prompt=_source_fallback_system_prompt(),
            user_prompt=_source_fallback_user_prompt(clean_question, source_chunks),
        )
        answer = str(payload.get("answer") or "").strip()
        citations = [str(item) for item in payload.get("citations", []) if str(item).strip()]
        allowed = {chunk.citation_label for chunk in source_chunks}
        citations = [citation for citation in citations if citation in allowed]
        evidence_status = str(payload.get("evidence_status") or "sufficient")

        if evidence_status != "sufficient" or not answer or not citations:
            answer = INSUFFICIENT_MESSAGE
            citations = []
            evidence_status = "insufficient"

        return self.repository.create(
            project_id=project_id,
            question=clean_question,
            answer=answer,
            citations=citations,
            source_provenance=citations,
            evidence_status=evidence_status,
        )

    def _answer_from_wiki(
        self,
        *,
        project_id: int,
        question: str,
        retrieved: list[RetrievedWikiSection],
    ) -> QARecord:
        payload = self.chat_provider.complete_json(
            system_prompt=_wiki_system_prompt(),
            user_prompt=_wiki_user_prompt(question, retrieved),
        )
        answer = str(payload.get("answer") or "").strip()
        citations = [str(item) for item in payload.get("citations", []) if str(item).strip()]
        allowed = {f"W:{section.section_uid}" for section in retrieved}
        citations = [citation for citation in citations if citation in allowed]
        source_provenance = _source_provenance(retrieved)
        evidence_status = str(payload.get("evidence_status") or "sufficient")

        if evidence_status != "sufficient" or not answer or not citations:
            answer = INSUFFICIENT_MESSAGE
            citations = []
            source_provenance = []
            evidence_status = "insufficient"

        return self.repository.create(
            project_id=project_id,
            question=question,
            answer=answer,
            citations=citations,
            source_provenance=source_provenance,
            evidence_status=evidence_status,
        )


def _wiki_system_prompt() -> str:
    return (
        "You answer questions from retrieved Domain Atlas Wiki sections first. "
        "Return strict JSON with answer, citations, and evidence_status. "
        "Citations must use the provided W:<section_uid> identifiers. "
        "If evidence is insufficient, set evidence_status to insufficient."
    )


def _wiki_user_prompt(question: str, retrieved: list[RetrievedWikiSection]) -> str:
    context = "\n\n".join(
        f"[W:{section.section_uid}] page={section.page_slug} "
        f"type={section.metadata.get('page_type', '')} "
        f"path={section.metadata.get('page_path', '')} "
        f"heading={section.heading}\n"
        f"{section.body_markdown}\n"
        f"Source provenance: {', '.join(section.source_citation_labels)}"
        for section in retrieved
    )
    return f"""
Question: {question}

Retrieved Wiki sections:
{context}

Return JSON:
{{
  "answer": "Chinese answer grounded only in the Wiki sections",
  "citations": ["W:agent#1"],
  "evidence_status": "sufficient"
}}
""".strip()


def _source_fallback_system_prompt() -> str:
    return (
        "You answer questions only from retrieved Domain Atlas source chunks. "
        "Return strict JSON with answer, citations, and evidence_status. "
        "If evidence is insufficient, set evidence_status to insufficient."
    )


def _source_fallback_user_prompt(question: str, retrieved: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[{chunk.citation_label}] {chunk.text}" for chunk in retrieved if chunk.citation_label
    )
    return f"""
Question: {question}

Retrieved chunks:
{context}

Return JSON:
{{
  "answer": "Chinese answer grounded only in the chunks",
  "citations": ["S1-C1"],
  "evidence_status": "sufficient"
}}
""".strip()


def _source_provenance(retrieved: list[RetrievedWikiSection]) -> list[str]:
    provenance: list[str] = []
    for section in retrieved:
        provenance.extend(section.source_citation_labels)
    return sorted({item for item in provenance if item})
