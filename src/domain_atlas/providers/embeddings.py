"""OpenAI-compatible embedding adapter."""

from __future__ import annotations

from typing import Any

import httpx

from domain_atlas.core.resilience import (
    ProviderRequestError,
    RetryObserver,
    RetryPolicy,
    execute_http_request,
    invalid_response_failure,
)


class EmbeddingProviderError(Exception):
    """Raised when embedding generation fails."""


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int | None = None,
        timeout_seconds: float = 45.0,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 1.0,
        retry_jitter_seconds: float = 0.2,
        retry_observer: RetryObserver | None = None,
        max_batch_size: int = 8,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.retry_policy = RetryPolicy(
            timeout_seconds=timeout_seconds,
            max_retries=max(0, max_retries),
            base_delay_seconds=retry_base_delay_seconds,
            jitter_seconds=retry_jitter_seconds,
        )
        self.retry_observer = retry_observer
        self.max_batch_size = max(1, max_batch_size)
        self.client = client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key.strip() or not self.base_url.strip():
            raise EmbeddingProviderError("Embedding provider is not configured.")

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.max_batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.max_batch_size]))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        body: dict[str, Any] = {"model": self.model, "input": texts}
        if self.dimensions:
            body["dimensions"] = self.dimensions
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            response = execute_http_request(
                provider="Embedding",
                operation="向量化",
                policy=self.retry_policy,
                observer=self.retry_observer,
                send=lambda timeout: self._post(headers=headers, body=body, timeout=timeout),
            )
        except ProviderRequestError as exc:
            raise EmbeddingProviderError(str(exc)) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError(
                str(
                    invalid_response_failure(
                        provider="Embedding", operation="向量化", observer=self.retry_observer
                    )
                )
            ) from exc

        rows = data.get("data")
        if not isinstance(rows, list):
            raise EmbeddingProviderError(
                str(
                    invalid_response_failure(
                        provider="Embedding", operation="向量化", observer=self.retry_observer
                    )
                )
            )
        vectors = [row.get("embedding") for row in rows if isinstance(row, dict)]
        if len(vectors) != len(texts) or not all(isinstance(vector, list) for vector in vectors):
            raise EmbeddingProviderError(
                str(
                    invalid_response_failure(
                        provider="Embedding", operation="向量化", observer=self.retry_observer
                    )
                )
            )
        return vectors

    def _post(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        if self.client is not None:
            return self.client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=body,
                timeout=timeout,
            )
        with httpx.Client(timeout=timeout) as client:
            return client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=body,
            )
