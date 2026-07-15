"""Chroma vector index wrapper."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Protocol

from domain_atlas.domain.artifacts import WikiSection
from domain_atlas.domain.sources import Chunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_uid: str
    text: str
    citation_label: str
    source_id: int
    distance: float | None
    metadata: dict


@dataclass(frozen=True)
class RetrievedWikiSection:
    section_uid: str
    page_slug: str
    heading: str
    body_markdown: str
    citations: list[str]
    source_chunk_uids: list[str]
    source_citation_labels: list[str]
    distance: float | None
    metadata: dict


class VectorIndex(Protocol):
    def upsert_chunks(
        self,
        *,
        project_id: int,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        ...

    def query(
        self,
        *,
        project_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedChunk]:
        ...

    def upsert_wiki_sections(
        self,
        *,
        project_id: int,
        sections: list[WikiSection],
        embeddings: list[list[float]],
    ) -> None:
        ...

    def query_wiki_sections(
        self,
        *,
        project_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedWikiSection]:
        ...


class ChromaVectorIndex:
    """Persist project chunk embeddings in local Chroma collections."""

    def __init__(self, persist_path: Path) -> None:
        self.persist_path = persist_path

    def upsert_chunks(
        self,
        *,
        project_id: int,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts must match.")

        import chromadb

        self.persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_path))
        collection = client.get_or_create_collection(name=f"domain_{project_id}_chunks")
        collection.upsert(
            ids=[chunk.chunk_uid for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "project_id": chunk.project_id,
                    "source_id": chunk.source_id,
                    "ordinal": chunk.ordinal,
                    "citation_label": chunk.citation_label,
                    **_scalar_metadata(chunk.metadata),
                }
                for chunk in chunks
            ],
        )

    def query(
        self,
        *,
        project_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedChunk]:
        import chromadb

        self.persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_path))
        collection = client.get_or_create_collection(name=f"domain_{project_id}_chunks")
        if collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, limit),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        retrieved: list[RetrievedChunk] = []
        for index, chunk_uid in enumerate(ids):
            metadata = metadatas[index] or {}
            retrieved.append(
                RetrievedChunk(
                    chunk_uid=str(chunk_uid),
                    text=str(documents[index] or ""),
                    citation_label=str(metadata.get("citation_label") or ""),
                    source_id=int(metadata.get("source_id") or 0),
                    distance=float(distances[index]) if distances else None,
                    metadata=dict(metadata),
                )
            )
        return retrieved

    def upsert_wiki_sections(
        self,
        *,
        project_id: int,
        sections: list[WikiSection],
        embeddings: list[list[float]],
    ) -> None:
        if not sections:
            return
        if len(sections) != len(embeddings):
            raise ValueError("Wiki section and embedding counts must match.")

        import chromadb

        self.persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_path))
        collection = client.get_or_create_collection(name=f"domain_{project_id}_wiki_sections")
        collection.upsert(
            ids=[section.section_uid for section in sections],
            documents=[section.body_markdown for section in sections],
            embeddings=embeddings,
            metadatas=[
                {
                    "project_id": section.project_id,
                    "page_id": section.page_id,
                    "page_slug": section.page_slug,
                    "page_type": section.page_type,
                    "page_path": section.page_path,
                    "heading": section.heading,
                    "ordinal": section.ordinal,
                    "citations": "|".join(section.citations),
                    "source_chunk_uids": "|".join(section.source_chunk_uids),
                    "source_citation_labels": "|".join(section.source_citation_labels),
                    "links": "|".join(section.links),
                }
                for section in sections
            ],
        )

    def query_wiki_sections(
        self,
        *,
        project_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedWikiSection]:
        import chromadb

        self.persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_path))
        collection = client.get_or_create_collection(name=f"domain_{project_id}_wiki_sections")
        if collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, limit),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        sections: list[RetrievedWikiSection] = []
        for index, section_uid in enumerate(ids):
            metadata = metadatas[index] or {}
            sections.append(
                RetrievedWikiSection(
                    section_uid=str(section_uid),
                    page_slug=str(metadata.get("page_slug") or ""),
                    heading=str(metadata.get("heading") or ""),
                    body_markdown=str(documents[index] or ""),
                    citations=_split_metadata_list(metadata.get("citations")),
                    source_chunk_uids=_split_metadata_list(metadata.get("source_chunk_uids")),
                    source_citation_labels=_split_metadata_list(
                        metadata.get("source_citation_labels")
                    ),
                    distance=float(distances[index]) if distances else None,
                    metadata=dict(metadata),
                )
            )
        return sections


def _scalar_metadata(metadata: dict) -> dict:
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }


def _split_metadata_list(value) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    return [part for part in value.split("|") if part]
