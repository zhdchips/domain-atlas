"""Document loaders for URL, Markdown, and text PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from domain_atlas.core.resilience import (
    ProviderRequestError,
    RetryObserver,
    RetryPolicy,
    execute_http_request,
)
from domain_atlas.ingestion.chunking import TextSegment


@dataclass(frozen=True)
class LoadedDocument:
    title: str
    raw_bytes: bytes
    normalized_text: str
    segments: list[TextSegment]
    metadata: dict[str, Any] = field(default_factory=dict)


class URLLoader:
    def __init__(
        self,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 1.0,
        retry_jitter_seconds: float = 0.2,
        retry_observer: RetryObserver | None = None,
    ) -> None:
        self.client = client
        self.retry_policy = RetryPolicy(
            timeout_seconds=timeout_seconds,
            max_retries=max(0, max_retries),
            base_delay_seconds=retry_base_delay_seconds,
            jitter_seconds=retry_jitter_seconds,
        )
        self.retry_observer = retry_observer

    def load(self, url: str) -> LoadedDocument:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        try:
            response = execute_http_request(
                provider="URL 资料",
                operation="抓取",
                policy=self.retry_policy,
                observer=self.retry_observer,
                send=lambda timeout: self._get(url=url, headers=headers, timeout=timeout),
            )
        except ProviderRequestError as exc:
            raise ValueError(str(exc)) from exc

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

    def _get(self, *, url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        if self.client is not None:
            return self.client.get(url, timeout=timeout, headers=headers)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            return client.get(url, headers=headers)


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
        if tag in {"script", "style", "noscript", "nav", "header", "footer", "aside", "form"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if (
            tag in {"script", "style", "noscript", "nav", "header", "footer", "aside", "form"}
            and self._skip_depth
        ):
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
