"""OpenAI-compatible chat adapter."""

from __future__ import annotations

import json
import re
import time
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
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
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

        response = self._post_with_retries(endpoint=endpoint, headers=headers, body=body)

        if response.status_code >= 400:
            message = _provider_error_message(response)
            raise ChatProviderError(
                f"Chat completion failed with HTTP {response.status_code}: {message}"
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ChatProviderError("Chat completion response shape was invalid.") from exc
        return _parse_json_object(str(content))

    def _post_with_retries(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
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
                last_error = exc
                if attempt + 1 >= attempts:
                    raise ChatProviderError("Chat completion request failed.") from exc
                _sleep_before_retry(self.retry_delay_seconds, attempt)
                continue

            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt + 1 >= attempts:
                return response
            _sleep_before_retry(self.retry_delay_seconds, attempt)

        raise ChatProviderError("Chat completion request failed.") from last_error


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


def _provider_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:240] or "provider returned an error"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            code = error.get("code")
            parts = [str(part) for part in (message, code) if part]
            if parts:
                return " / ".join(parts)[:240]
    return json.dumps(payload, ensure_ascii=False)[:240]


def _sleep_before_retry(base_delay: float, attempt: int) -> None:
    if base_delay <= 0:
        return
    time.sleep(base_delay * (2**attempt))
