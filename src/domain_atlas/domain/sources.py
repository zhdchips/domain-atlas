"""Source and chunk models with SQLite repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class Source:
    id: int
    project_id: int
    source_type: str
    title: str
    locator: str
    raw_path: str
    normalized_path: str
    checksum: str
    status: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CreateSource:
    project_id: int
    source_type: str
    title: str
    locator: str
    raw_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    id: int
    chunk_uid: str
    project_id: int
    source_id: int
    ordinal: int
    text: str
    citation_label: str
    metadata: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class CreateChunk:
    chunk_uid: str
    project_id: int
    source_id: int
    ordinal: int
    text: str
    citation_label: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SourceRepository:
    """SQLite-backed source repository."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(self, payload: CreateSource) -> Source:
        with connect(self.database_path) as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM sources
                WHERE project_id = ? AND locator = ?
                """,
                (payload.project_id, payload.locator),
            ).fetchone()
            if existing:
                return _row_to_source(existing)

            cursor = connection.execute(
                """
                INSERT INTO sources (
                    project_id, source_type, title, locator, raw_path, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.project_id,
                    payload.source_type,
                    payload.title.strip() or payload.locator,
                    payload.locator.strip(),
                    payload.raw_path,
                    json.dumps(payload.metadata, ensure_ascii=False),
                ),
            )
            source_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_source(row)

    def list_for_project(self, project_id: int) -> list[Source]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM sources
                WHERE project_id = ?
                ORDER BY id DESC
                """,
                (project_id,),
            ).fetchall()
        return [_row_to_source(row) for row in rows]

    def get(self, source_id: int) -> Source | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE id = ?",
                (source_id,),
            ).fetchone()
        return _row_to_source(row) if row else None

    def update_raw_path(self, source_id: int, raw_path: str) -> Source:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sources
                SET raw_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (raw_path, source_id),
            )
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_source(row)

    def update_ingested(
        self,
        source_id: int,
        *,
        raw_path: str,
        normalized_path: str,
        checksum: str,
        metadata: dict[str, Any],
    ) -> Source:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sources
                SET raw_path = ?,
                    normalized_path = ?,
                    checksum = ?,
                    status = 'ingested',
                    metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    raw_path,
                    normalized_path,
                    checksum,
                    json.dumps(metadata, ensure_ascii=False),
                    source_id,
                ),
            )
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_source(row)

    def update_failed(self, source_id: int, message: str) -> Source:
        source = self.get(source_id)
        metadata = dict(source.metadata if source else {})
        metadata["error"] = message
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sources
                SET status = 'failed',
                    metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(metadata, ensure_ascii=False), source_id),
            )
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_source(row)

    def update_excluded(
        self,
        source_id: int,
        *,
        raw_path: str,
        normalized_path: str,
        checksum: str,
        metadata: dict[str, Any],
        reason: str,
    ) -> Source:
        updated_metadata = {**metadata, "exclusion_reason": reason}
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sources
                SET raw_path = ?,
                    normalized_path = ?,
                    checksum = ?,
                    status = 'excluded',
                    metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    raw_path,
                    normalized_path,
                    checksum,
                    json.dumps(updated_metadata, ensure_ascii=False),
                    source_id,
                ),
            )
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_source(row)


class ChunkRepository:
    """SQLite-backed chunk repository."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def replace_for_source(self, source_id: int, chunks: list[CreateChunk]) -> list[Chunk]:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            ids: list[int] = []
            for chunk in chunks:
                cursor = connection.execute(
                    """
                    INSERT INTO chunks (
                        chunk_uid,
                        project_id,
                        source_id,
                        ordinal,
                        text,
                        citation_label,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_uid,
                        chunk.project_id,
                        chunk.source_id,
                        chunk.ordinal,
                        chunk.text,
                        chunk.citation_label,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    ),
                )
                ids.append(int(cursor.lastrowid))
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(
                f"SELECT * FROM chunks WHERE id IN ({placeholders}) ORDER BY ordinal ASC",
                ids,
            ).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def list_for_source(self, source_id: int) -> list[Chunk]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE source_id = ? ORDER BY ordinal ASC",
                (source_id,),
            ).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def count_for_project(self, project_id: int) -> int:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM chunks WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["count"])

    def list_for_project(self, project_id: int, *, limit: int | None = None) -> list[Chunk]:
        query = """
            SELECT *
            FROM chunks
            WHERE project_id = ?
            ORDER BY source_id ASC, ordinal ASC
        """
        params: list[int] = [project_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with connect(self.database_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_chunk(row) for row in rows]


def _row_to_source(row) -> Source:
    return Source(
        id=int(row["id"]),
        project_id=int(row["project_id"]),
        source_type=str(row["source_type"]),
        title=str(row["title"]),
        locator=str(row["locator"]),
        raw_path=str(row["raw_path"]),
        normalized_path=str(row["normalized_path"]),
        checksum=str(row["checksum"]),
        status=str(row["status"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_chunk(row) -> Chunk:
    return Chunk(
        id=int(row["id"]),
        chunk_uid=str(row["chunk_uid"]),
        project_id=int(row["project_id"]),
        source_id=int(row["source_id"]),
        ordinal=int(row["ordinal"]),
        text=str(row["text"]),
        citation_label=str(row["citation_label"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=str(row["created_at"]),
    )
