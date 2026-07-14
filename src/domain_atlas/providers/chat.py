"""OpenAI-compatible chat adapter."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx


class ChatProviderError(Exception):
    """Raised when chat completion fails or returns invalid JSON."""


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.client = client

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key.strip() or not self.base_url.strip():
            raise ChatProviderError("Chat provider is not configured.")

        endpoint = (
            f"{self.base_url}/chat/completions"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/chat/completions"
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            if self.client is not None:
                response = self.client.post(
                    endpoint,
                    headers=headers,
                    json=body,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(endpoint, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ChatProviderError("Chat completion request failed.") from exc

        if response.status_code >= 400:
            raise ChatProviderError(f"Chat completion failed with HTTP {response.status_code}.")

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ChatProviderError("Chat completion response shape was invalid.") from exc
        return _parse_json_object(str(content))


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ChatProviderError("Chat completion did not return valid JSON.") from exc
    if not isinstance(data, dict):
        raise ChatProviderError("Chat completion JSON must be an object.")
    return data
