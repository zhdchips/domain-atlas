"""Document loaders for URL, Markdown, and text PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from domain_atlas.ingestion.chunking import TextSegment


@dataclass(frozen=True)
class LoadedDocument:
    title: str
    raw_bytes: bytes
    normalized_text: str
    segments: list[TextSegment]
    metadata: dict[str, Any] = field(default_factory=dict)


class URLLoader:
    def __init__(self, client: httpx.Client | None = None, timeout_seconds: float = 30.0) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds

    def load(self, url: str) -> LoadedDocument:
        try:
            if self.client is not None:
                response = self.client.get(url, timeout=self.timeout_seconds)
            else:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(url)
        except httpx.HTTPError as exc:
            raise ValueError("URL fetch failed.") from exc
        if response.status_code >= 400:
            raise ValueError(f"URL fetch failed with HTTP {response.status_code}.")

        raw = response.content
        parser = _TextHTMLParser()
        parser.feed(response.text)
        title = parser.title or url
        text = parser.text
        return LoadedDocument(
            title=title,
            raw_bytes=raw,
            normalized_text=text,
            segments=[TextSegment(text=text, metadata={"locator": url})],
            metadata={"content_type": response.headers.get("content-type", ""), "title": title},
        )


class MarkdownLoader:
    def load(self, path: Path) -> LoadedDocument:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        title = _first_markdown_heading(text) or path.stem
        return LoadedDocument(
            title=title,
            raw_bytes=raw,
            normalized_text=text,
            segments=[TextSegment(text=text, metadata={"path": str(path)})],
            metadata={"title": title},
        )


class PDFLoader:
    def load(self, path: Path) -> LoadedDocument:
        raw = path.read_bytes()
        reader = PdfReader(path)
        segments: list[TextSegment] = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                segments.append(TextSegment(text=text, metadata={"page": page_index}))
        normalized = "\n\n".join(segment.text for segment in segments)
        title = path.stem
        return LoadedDocument(
            title=title,
            raw_bytes=raw,
            normalized_text=normalized,
            segments=segments,
            metadata={"title": title, "page_count": len(reader.pages)},
        )


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    @property
    def title(self) -> str:
        return " ".join(" ".join(self._title_parts).split())

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._text_parts).split())

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._skip_depth:
            return
        if self._in_title:
            self._title_parts.append(text)
        else:
            self._text_parts.append(text)


def _first_markdown_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""
