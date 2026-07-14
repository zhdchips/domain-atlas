"""OpenAI-compatible embedding adapter."""

from __future__ import annotations

from typing import Any

import httpx


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
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self.client = client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key.strip() or not self.base_url.strip():
            raise EmbeddingProviderError("Embedding provider is not configured.")

        body: dict[str, Any] = {"model": self.model, "input": texts}
        if self.dimensions:
            body["dimensions"] = self.dimensions
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            if self.client is not None:
                response = self.client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=body,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json=body,
                    )
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError("Embedding request failed.") from exc

        if response.status_code >= 400:
            raise EmbeddingProviderError(f"Embedding request failed with HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError("Embedding response was invalid JSON.") from exc

        rows = data.get("data")
        if not isinstance(rows, list):
            raise EmbeddingProviderError("Embedding response did not include data rows.")
        vectors = [row.get("embedding") for row in rows if isinstance(row, dict)]
        if len(vectors) != len(texts) or not all(isinstance(vector, list) for vector in vectors):
            raise EmbeddingProviderError("Embedding response shape did not match input texts.")
        return vectors
