from __future__ import annotations

import json

import httpx

from domain_atlas.providers.embeddings import OpenAICompatibleEmbeddingProvider


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
