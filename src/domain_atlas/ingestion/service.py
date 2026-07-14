"""Source ingestion service."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import httpx

from domain_atlas.domain.sources import (
    Chunk,
    ChunkRepository,
    CreateChunk,
    Source,
    SourceRepository,
)
from domain_atlas.ingestion.chunking import chunk_segments
from domain_atlas.ingestion.loaders import LoadedDocument, MarkdownLoader, PDFLoader, URLLoader
from domain_atlas.providers.vector_index import VectorIndex


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class IngestionService:
    """Normalize sources, create chunks, embed them, and index vectors."""

    def __init__(
        self,
        *,
        database_path: Path,
        data_dir: Path,
        embedding_provider: EmbeddingProvider,
        vector_index: VectorIndex,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.source_repository = SourceRepository(database_path)
        self.chunk_repository = ChunkRepository(database_path)
        self.data_dir = data_dir
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index
        self.http_client = http_client

    def ingest_source(self, source_id: int) -> tuple[Source, list[Chunk]]:
        source = self.source_repository.get(source_id)
        if source is None:
            raise ValueError("Source not found.")

        try:
            document = self._load(source)
            if not document.normalized_text.strip():
                raise ValueError("Source did not contain extractable text.")
            checksum = hashlib.sha256(document.raw_bytes).hexdigest()
            raw_path, normalized_path = self._write_artifacts(source, document)
            text_chunks = chunk_segments(
                source_id=source.id,
                source_checksum=checksum,
                segments=document.segments,
            )
            if not text_chunks:
                raise ValueError("Source did not produce any chunks.")

            chunk_rows = self.chunk_repository.replace_for_source(
                source.id,
                [
                    CreateChunk(
                        chunk_uid=chunk.chunk_uid,
                        project_id=source.project_id,
                        source_id=source.id,
                        ordinal=chunk.ordinal,
                        text=chunk.text,
                        citation_label=chunk.citation_label,
                        metadata={
                            **chunk.metadata,
                            "source_title": document.title or source.title,
                            "source_type": source.source_type,
                            "locator": source.locator,
                        },
                    )
                    for chunk in text_chunks
                ],
            )
            embeddings = self.embedding_provider.embed_texts([chunk.text for chunk in chunk_rows])
            self.vector_index.upsert_chunks(
                project_id=source.project_id,
                chunks=chunk_rows,
                embeddings=embeddings,
            )
            updated = self.source_repository.update_ingested(
                source.id,
                raw_path=str(raw_path),
                normalized_path=str(normalized_path),
                checksum=checksum,
                metadata={**source.metadata, **document.metadata, "chunk_count": len(chunk_rows)},
            )
            return updated, chunk_rows
        except Exception as exc:
            self.source_repository.update_failed(source.id, str(exc))
            raise

    def _load(self, source: Source) -> LoadedDocument:
        if source.source_type == "url":
            return URLLoader(client=self.http_client).load(source.locator)
        raw_path = Path(source.raw_path)
        if source.source_type == "markdown":
            return MarkdownLoader().load(raw_path)
        if source.source_type == "pdf":
            return PDFLoader().load(raw_path)
        raise ValueError(f"Unsupported source type: {source.source_type}")

    def _write_artifacts(self, source: Source, document: LoadedDocument) -> tuple[Path, Path]:
        source_dir = self.data_dir / "sources" / str(source.project_id) / str(source.id)
        source_dir.mkdir(parents=True, exist_ok=True)
        extension = {
            "url": ".html",
            "markdown": ".md",
            "pdf": ".pdf",
        }.get(source.source_type, ".bin")
        raw_path = source_dir / f"raw{extension}"
        normalized_path = source_dir / "normalized.txt"
        raw_path.write_bytes(document.raw_bytes)
        normalized_path.write_text(document.normalized_text, encoding="utf-8")
        return raw_path, normalized_path
