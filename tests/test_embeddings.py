from __future__ import annotations

import json

import httpx

from domain_atlas.providers.embeddings import (
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
)


def test_openai_compatible_embedding_provider_parses_vectors():
    expected_key = "not-a-real-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://embedding.example.com/v1/embeddings"
        assert request.headers["authorization"] == f"Bearer {expected_key}"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "text-embedding-v4"
        assert body["dimensions"] == 2
        assert body["input"] == ["hello", "world"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2]},
                    {"embedding": [0.3, 0.4]},
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        api_key=expected_key,
        base_url="https://embedding.example.com/v1",
        model="text-embedding-v4",
        dimensions=2,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.embed_texts(["hello", "world"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_embedding_provider_batches_large_inputs():
    calls: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        inputs = body["input"]
        calls.append(inputs)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [float(len(calls)), float(index)]}
                    for index, _text in enumerate(inputs)
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        api_key="not-a-real-key",
        base_url="https://embedding.example.com/v1",
        model="text-embedding-v4",
        dimensions=2,
        max_batch_size=4,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    vectors = provider.embed_texts([f"text-{index}" for index in range(10)])

    assert calls == [
        ["text-0", "text-1", "text-2", "text-3"],
        ["text-4", "text-5", "text-6", "text-7"],
        ["text-8", "text-9"],
    ]
    assert len(vectors) == 10
    assert vectors[0] == [1.0, 0.0]
    assert vectors[-1] == [3.0, 1.0]


def test_embedding_provider_retries_transient_response_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        api_key="not-a-real-key",
        base_url="https://embedding.example.com/v1",
        model="text-embedding-v4",
        max_retries=1,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.embed_texts(["hello"]) == [[0.1, 0.2]]
    assert calls["count"] == 2


def test_embedding_provider_exhausts_network_retries_without_leaking_secret():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("api_key=not-a-real-key", request=request)

    provider = OpenAICompatibleEmbeddingProvider(
        api_key="not-a-real-key",
        base_url="https://embedding.example.com/v1",
        model="text-embedding-v4",
        max_retries=1,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.embed_texts(["hello"])
    except EmbeddingProviderError as exc:
        assert "Embedding向量化网络连接失败" in str(exc)
        assert "not-a-real-key" not in str(exc)
    else:
        raise AssertionError("Expected retry exhaustion.")


def test_embedding_provider_does_not_retry_access_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, text="secret provider response")

    provider = OpenAICompatibleEmbeddingProvider(
        api_key="not-a-real-key",
        base_url="https://embedding.example.com/v1",
        model="text-embedding-v4",
        max_retries=2,
        retry_base_delay_seconds=0,
        retry_jitter_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.embed_texts(["hello"])
    except EmbeddingProviderError as exc:
        assert "配置或访问受限" in str(exc)
        assert "secret provider response" not in str(exc)
    else:
        raise AssertionError("Expected non-retryable access failure.")
    assert calls["count"] == 1
