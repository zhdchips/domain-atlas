from __future__ import annotations

import json

import httpx

from domain_atlas.discovery.exa import ExaSearchProvider, SourceDiscoveryError


def test_exa_provider_normalizes_search_results():
    expected_key = "not-a-real-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.exa.ai/search"
        assert request.headers["x-api-key"] == expected_key
        body = json.loads(request.content.decode("utf-8"))
        assert body["query"] == "LLM Agents"
        assert body["numResults"] == 2
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "src-1",
                        "title": "Official Agent Docs",
                        "url": "https://docs.example.com/agents",
                        "summary": "Authoritative documentation for agents.",
                        "author": "Example",
                        "publishedDate": "2026-01-01",
                        "score": 0.91,
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ExaSearchProvider(api_key=expected_key, client=client)

    candidates = provider.search("LLM Agents", limit=2)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.provider == "exa"
    assert candidate.provider_source_id == "src-1"
    assert candidate.title == "Official Agent Docs"
    assert candidate.source_type == "official_docs"
    assert candidate.authority_score > 0.7
    assert "官方" in candidate.authority_reason
    assert candidate.metadata["provider_rank"] == 1


def test_exa_provider_recognizes_chinese_docs_and_encyclopedia_sources():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "aliyun-help",
                        "title": "核心概念定义与逻辑结构-智能数据建设与治理 Dataphin-阿里云",
                        "url": "https://help.aliyun.com/zh/dataphin/fullmanaged/product-overview/logical-structure-that",
                        "summary": "Dataphin product overview.",
                    },
                    {
                        "id": "baike",
                        "title": "Dataphin_百度百科",
                        "url": "https://baike.baidu.com/item/Dataphin/52936374",
                        "summary": "Dataphin encyclopedia entry.",
                    },
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ExaSearchProvider(api_key="not-a-real-key", client=client)

    candidates = provider.search("Dataphin", limit=2)

    assert candidates[0].source_type == "official_docs"
    assert candidates[0].authority_score >= 0.65
    assert candidates[1].source_type == "encyclopedia"
    assert candidates[1].authority_score >= 0.65


def test_exa_provider_requires_api_key():
    provider = ExaSearchProvider(api_key="")

    try:
        provider.search("LLM Agents", limit=1)
    except SourceDiscoveryError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected missing API key to fail.")


def test_exa_provider_retries_transient_overload():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "temporarily overloaded"})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "src-1",
                        "title": "Official Agent Docs",
                        "url": "https://docs.example.com/agents",
                    }
                ]
            },
        )

    provider = ExaSearchProvider(
        api_key="not-a-real-key",
        max_retries=1,
        retry_delay_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert len(provider.search("LLM Agents", limit=1)) == 1
    assert calls["count"] == 2


def test_exa_provider_reports_connection_error_kind_after_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    provider = ExaSearchProvider(
        api_key="not-a-real-key",
        max_retries=1,
        retry_delay_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.search("LLM Agents", limit=1)
    except SourceDiscoveryError as exc:
        assert str(exc) == "Exa search connection failed after 2 attempts: ConnectError."
    else:
        raise AssertionError("Expected connection failure to be raised.")
