from __future__ import annotations

from domain_atlas.domain.sources import Chunk
from domain_atlas.providers.vector_index import ChromaVectorIndex


def test_chroma_vector_index_upserts_chunks(tmp_path):
    index = ChromaVectorIndex(tmp_path / "chroma")
    chunk = Chunk(
        id=1,
        chunk_uid="chunk:test",
        project_id=1,
        source_id=1,
        ordinal=1,
        text="hello world",
        citation_label="S1-C1",
        metadata={"source_title": "Test Source"},
        created_at="2026-01-01 00:00:00",
    )

    index.upsert_chunks(project_id=1, chunks=[chunk], embeddings=[[0.1, 0.2]])

    import chromadb

    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_collection("domain_1_chunks")
    assert collection.count() == 1

    hits = index.query(project_id=1, query_embedding=[0.1, 0.2], limit=1)
    assert len(hits) == 1
    assert hits[0].citation_label == "S1-C1"
    assert hits[0].text == "hello world"
