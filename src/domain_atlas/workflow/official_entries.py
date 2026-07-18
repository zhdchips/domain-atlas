"""Bounded inspection of regional entries linked from brand-aligned official pages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

from domain_atlas.domain.source_candidates import SourceCandidateDraft


class OfficialEntryInspector(Protocol):
    """Discover regional service links from already-selected first-party pages."""

    def inspect(
        self,
        *,
        target_region: str,
        candidates: list[SourceCandidateDraft],
    ) -> list[SourceCandidateDraft]:
        ...


@dataclass(frozen=True)
class _Anchor:
    href: str
    label: str


class HttpOfficialEntryInspector:
    """Inspect at most two brand-aligned pages; failures never create authority."""

    def __init__(self, *, timeout_seconds: float = 10.0, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def inspect(
        self,
        *,
        target_region: str,
        candidates: list[SourceCandidateDraft],
    ) -> list[SourceCandidateDraft]:
        entries: list[SourceCandidateDraft] = []
        seen_targets: set[str] = set()
        eligible = [
            candidate
            for candidate in candidates
            if candidate.metadata.get("brand_domain_candidate") is True
            and candidate.metadata.get("region_match") != "cross_region"
        ][:2]
        for candidate in eligible:
            html = self._fetch(candidate.url)
            if not html:
                continue
            for anchor in _extract_anchors(html):
                target_url = urljoin(candidate.url, anchor.href)
                target_region_for_link = _link_region(anchor, target_url)
                if target_region_for_link != target_region or target_url in seen_targets:
                    continue
                if not _is_supported_entry_target(candidate.url, target_url):
                    continue
                seen_targets.add(target_url)
                entries.append(_entry_draft(candidate, target_url, anchor, target_region))
        return entries

    def _fetch(self, url: str) -> str:
        try:
            if self.client is not None:
                response = self.client.get(
                    url,
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                    headers=_headers(),
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                    response = client.get(url, headers=_headers())
        except httpx.HTTPError:
            return ""
        content_type = response.headers.get("content-type", "").lower()
        if response.status_code < 200 or response.status_code >= 300 or "html" not in content_type:
            return ""
        return response.text


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "DomainAtlasOfficialEntryInspector/0.1",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _entry_draft(
    discovery: SourceCandidateDraft,
    target_url: str,
    anchor: _Anchor,
    region: str,
) -> SourceCandidateDraft:
    digest = hashlib.sha256(f"{discovery.url}|{target_url}".encode("utf-8")).hexdigest()[:16]
    target_host = urlparse(target_url).netloc.lower()
    social_or_app = _is_social_or_app_target(target_url)
    label = anchor.label or target_host
    return SourceCandidateDraft(
        provider="official_entry",
        provider_source_id=f"official-entry:{digest}",
        title=f"{label}官方服务入口",
        url=target_url,
        snippet=f"由官方站点 {discovery.url} 的地区入口链接发现。",
        source_type="web",
        publisher=urlparse(discovery.url).netloc.lower(),
        authority_score=max(discovery.authority_score, 0.8),
        authority_reason="品牌官方站点的地区入口链接",
        metadata={
            "source_role": "first_party",
            "source_region": region,
            "official_entry_evidence_type": "official_regional_link",
            "official_entry_discovery_url": discovery.url,
            "official_entry_target_url": target_url,
            "official_entry_target_label": label,
            "official_entry_region": region,
            "official_entry_verification": "requires_manual_confirmation" if social_or_app else "verified",
            "auto_ingestible": not social_or_app,
            "source_family": f"official-entry:{discovery.url.rstrip('/')}->{target_host}",
        },
    )


def _is_supported_entry_target(discovery_url: str, target_url: str) -> bool:
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if _is_social_or_app_target(target_url):
        return True
    return _registrable_domain(discovery_url) == _registrable_domain(target_url)


def _is_social_or_app_target(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(marker in host for marker in ("weixin.qq.com", "weixin", "wechat", "douyin", "xiaohongshu"))


def _registrable_domain(url: str) -> str:
    parts = urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"com.cn", "com.tw", "com.hk", "co.jp"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _link_region(anchor: _Anchor, url: str) -> str:
    combined = f"{anchor.label} {url}".lower()
    if any(marker in combined for marker in ("台湾", "台灣", "taiwan", ".tw")):
        return "TW"
    if any(marker in combined for marker in ("香港", "hong kong", ".hk")):
        return "HK"
    if any(
        marker in combined
        for marker in ("中国", "中國", "大陆", "大陸", "广州", "廣州", "北京", "上海", "深圳", "成都", ".cn")
    ):
        return "CN"
    return ""


def _extract_anchors(html: str) -> list[_Anchor]:
    parser = _AnchorParser()
    parser.feed(html)
    return parser.anchors


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[_Anchor] = []
        self._href = ""
        self._label_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        self._href = attributes.get("href") or ""
        self._label_parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._label_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.anchors.append(_Anchor(href=self._href, label=" ".join(self._label_parts).strip()))
            self._href = ""
            self._label_parts = []
