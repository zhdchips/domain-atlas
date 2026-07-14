"""Chroma vector index wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from domain_atlas.domain.sources import Chunk


class VectorIndex(Protocol):
    def upsert_chunks(
        self,
        *,
        project_id: int,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
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


def _scalar_metadata(metadata: dict) -> dict:
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
