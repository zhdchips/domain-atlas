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


def test_exa_provider_requires_api_key():
    provider = ExaSearchProvider(api_key="")

    try:
        provider.search("LLM Agents", limit=1)
    except SourceDiscoveryError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected missing API key to fail.")
