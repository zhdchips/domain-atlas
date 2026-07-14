"""Source candidate models and repository."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class SourceCandidateDraft:
    provider: str
    provider_source_id: str
    title: str
    url: str
    snippet: str
    source_type: str = "web"
    publisher: str = ""
    author: str = ""
    published_at: str = ""
    authority_score: float = 0.0
    authority_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    project_id: int
    provider: str
    provider_source_id: str
    title: str
    url: str
    snippet: str
    source_type: str
    publisher: str
    author: str
    published_at: str
    authority_score: float
    authority_reason: str
    status: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class SourceCandidateRepository:
    """SQLite-backed repository for discovered source candidates."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def replace_discovered(
        self,
        project_id: int,
        drafts: list[SourceCandidateDraft],
    ) -> list[SourceCandidate]:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                DELETE FROM source_candidates
                WHERE project_id = ? AND status = 'discovered'
                """,
                (project_id,),
            )
            ids: list[int] = []
            for draft in drafts:
                cursor = connection.execute(
                    """
                    INSERT INTO source_candidates (
                        project_id,
                        provider,
                        provider_source_id,
                        title,
                        url,
                        snippet,
                        source_type,
                        publisher,
                        author,
                        published_at,
                        authority_score,
                        authority_reason,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        draft.provider,
                        draft.provider_source_id,
                        draft.title.strip(),
                        draft.url.strip(),
                        draft.snippet.strip(),
                        draft.source_type,
                        draft.publisher,
                        draft.author,
                        draft.published_at,
                        draft.authority_score,
                        draft.authority_reason,
                        json.dumps(draft.metadata, ensure_ascii=False),
                    ),
                )
                ids.append(int(cursor.lastrowid))

            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(
                f"""
                SELECT *
                FROM source_candidates
                WHERE id IN ({placeholders})
                ORDER BY authority_score DESC, id ASC
                """,
                ids,
            ).fetchall()
        return [_row_to_candidate(row) for row in rows]

    def list_for_project(
        self,
        project_id: int,
        *,
        limit: int | None = None,
    ) -> list[SourceCandidate]:
        query = """
            SELECT *
            FROM source_candidates
            WHERE project_id = ?
            ORDER BY
                CASE status
                    WHEN 'accepted' THEN 0
                    WHEN 'discovered' THEN 1
                    ELSE 2
                END,
                authority_score DESC,
                id ASC
        """
        params: list[int] = [project_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with connect(self.database_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_candidate(row) for row in rows]

    def accept(self, project_id: int, candidate_id: int) -> SourceCandidate | None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE source_candidates
                SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND project_id = ?
                """,
                (candidate_id, project_id),
            )
            row = connection.execute(
                """
                SELECT *
                FROM source_candidates
                WHERE id = ? AND project_id = ?
                """,
                (candidate_id, project_id),
            ).fetchone()
        return _row_to_candidate(row) if row else None


def _row_to_candidate(row) -> SourceCandidate:
    return SourceCandidate(
        id=int(row["id"]),
        project_id=int(row["project_id"]),
        provider=str(row["provider"]),
        provider_source_id=str(row["provider_source_id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        snippet=str(row["snippet"]),
        source_type=str(row["source_type"]),
        publisher=str(row["publisher"]),
        author=str(row["author"]),
        published_at=str(row["published_at"]),
        authority_score=float(row["authority_score"]),
        authority_reason=str(row["authority_reason"]),
        status=str(row["status"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
