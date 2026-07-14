"""Text chunking with stable citation metadata."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TextSegment:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextChunk:
    chunk_uid: str
    ordinal: int
    text: str
    citation_label: str
    metadata: dict[str, Any]


def chunk_segments(
    *,
    source_id: int,
    source_checksum: str,
    segments: list[TextSegment],
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[TextChunk]:
    """Split text segments into stable chunks."""
    chunks: list[TextChunk] = []
    ordinal = 1
    step = max(chunk_size - overlap, 1)
    for segment_index, segment in enumerate(segments, start=1):
        text = _collapse_whitespace(segment.text)
        if not text:
            continue
        for start in range(0, len(text), step):
            piece = text[start : start + chunk_size].strip()
            if not piece:
                continue
            digest = hashlib.sha256(
                f"{source_id}:{source_checksum}:{ordinal}:{piece}".encode("utf-8")
            ).hexdigest()[:24]
            metadata = {
                "segment_index": segment_index,
                "char_start": start,
                "char_end": start + len(piece),
                **segment.metadata,
            }
            chunks.append(
                TextChunk(
                    chunk_uid=f"chunk:{digest}",
                    ordinal=ordinal,
                    text=piece,
                    citation_label=f"S{source_id}-C{ordinal}",
                    metadata=metadata,
                )
            )
            ordinal += 1
            if start + chunk_size >= len(text):
                break
    return chunks


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())
