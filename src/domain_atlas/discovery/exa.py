"""Exa source discovery adapter."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

import httpx

from domain_atlas.domain.source_candidates import SourceCandidateDraft


class SourceDiscoveryError(Exception):
    """Raised when source discovery cannot return usable candidates."""


class ExaSearchProvider:
    """Search web sources with Exa and normalize candidates for Domain Atlas."""

    provider_name = "exa"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.exa.ai",
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        if not self.api_key.strip():
            raise SourceDiscoveryError("Exa API key is not configured.")
        request_limit = max(1, limit)
        payload = {
            "query": query.strip(),
            "numResults": request_limit,
            "contents": {
                "summary": True,
                "highlights": True,
                "text": False,
            },
        }
        data = self._post_search(payload)
        results = data.get("results")
        if not isinstance(results, list):
            raise SourceDiscoveryError("Exa returned an invalid result payload.")

        candidates = [
            self._normalize_result(item, rank=index)
            for index, item in enumerate(results[:request_limit], start=1)
            if isinstance(item, dict)
        ]
        if not candidates:
            raise SourceDiscoveryError("Exa returned no usable source candidates.")
        return candidates

    def _post_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        try:
            if self.client is not None:
                response = self.client.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        f"{self.base_url}/search",
                        headers=headers,
                        json=payload,
                    )
        except httpx.TimeoutException as exc:
            raise SourceDiscoveryError("Exa search timed out.") from exc
        except httpx.HTTPError as exc:
            raise SourceDiscoveryError("Exa search request failed.") from exc

        if response.status_code in {401, 403}:
            raise SourceDiscoveryError("Exa search is not configured correctly.")
        if response.status_code == 429:
            raise SourceDiscoveryError("Exa search rate limit exceeded.")
        if response.status_code >= 400:
            raise SourceDiscoveryError(f"Exa search failed with HTTP {response.status_code}.")

        try:
            data = response.json()
        except ValueError as exc:
            raise SourceDiscoveryError("Exa search returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise SourceDiscoveryError("Exa search returned invalid JSON.")
        return data

    def _normalize_result(self, item: dict[str, Any], *, rank: int) -> SourceCandidateDraft:
        title = _optional_str(item.get("title"))
        url = _optional_str(item.get("url"))
        summary = _optional_str(item.get("summary"))
        highlights = _string_list(item.get("highlights"))
        snippet = _first_text([summary] + highlights)
        if not title or not url:
            raise SourceDiscoveryError("Exa result was missing title or URL.")

        source_type = _guess_source_type(url, title)
        publisher = _optional_str(item.get("author")) or _publisher_from_url(url)
        score, reason = _authority_score(url, source_type, publisher)
        provider_source_id = _optional_str(item.get("id")) or _stable_source_id(url)

        return SourceCandidateDraft(
            provider=self.provider_name,
            provider_source_id=provider_source_id,
            title=title,
            url=url,
            snippet=snippet,
            source_type=source_type,
            publisher=publisher,
            author=_optional_str(item.get("author")),
            published_at=_optional_str(item.get("publishedDate")),
            authority_score=score,
            authority_reason=reason,
            metadata={
                "provider_rank": rank,
                "provider_score": item.get("score"),
                "highlights": highlights,
            },
        )


def _optional_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _first_text(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _stable_source_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"exa:{digest}"


def _publisher_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _guess_source_type(url: str, title: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    lowered = f"{host} {path} {title}".lower()
    if "arxiv.org" in host or "doi.org" in host or "paper" in lowered:
        return "paper"
    if "github.com" in host:
        return "repository"
    if "wikipedia.org" in host or "baike.baidu.com" in host or "百科" in title:
        return "encyclopedia"
    if (
        "docs." in host
        or host.startswith("help.")
        or host.startswith("developer.")
        or "documentation" in lowered
        or "docs" in lowered
        or "帮助文档" in title
        or "帮助中心" in title
        or "产品文档" in title
        or "白皮书" in title
        or "/help/" in path
        or "/product/" in path
        or "product-overview" in path
    ):
        return "official_docs"
    if any(part in host for part in (".edu", ".gov", "ac.", "edu.")):
        return "institution"
    return "web"


def _authority_score(url: str, source_type: str, publisher: str) -> tuple[float, str]:
    host = urlparse(url).netloc.lower()
    score = 0.45
    reasons: list[str] = []

    if source_type in {"official_docs", "institution"}:
        score += 0.3
        reasons.append("官方或机构资料")
    elif source_type == "paper":
        score += 0.25
        reasons.append("论文或研究资料")
    elif source_type == "repository":
        score += 0.15
        reasons.append("代码仓库资料")
    elif source_type == "encyclopedia":
        score += 0.15
        reasons.append("百科资料")

    trusted_host_markers = (
        ".edu",
        ".gov",
        "arxiv.org",
        "docs.",
        "help.",
        "developer.",
        "github.com",
        "wikipedia.org",
        "baike.baidu.com",
    )
    if any(part in host for part in trusted_host_markers):
        score += 0.15
        reasons.append("来源域名可信度较高")

    if publisher:
        score += 0.05
        reasons.append("包含发布者信息")

    bounded = min(score, 1.0)
    return bounded, "；".join(reasons) if reasons else "通用网页资料，需人工确认权威性"
