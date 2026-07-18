"""OpenAI-compatible chat adapter."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from domain_atlas.core.resilience import (
    ProviderRequestError,
    RetryObserver,
    RetryPolicy,
    execute_http_request,
    invalid_response_failure,
)

class ChatProviderError(Exception):
    """Raised when chat completion fails or returns invalid JSON."""


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int | None = None,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 1.0,
        retry_jitter_seconds: float = 0.2,
        retry_delay_seconds: float | None = None,
        retry_observer: RetryObserver | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.retry_policy = RetryPolicy(
            timeout_seconds=timeout_seconds,
            max_retries=max(0, max_retries),
            base_delay_seconds=(
                retry_delay_seconds
                if retry_delay_seconds is not None
                else retry_base_delay_seconds
            ),
            jitter_seconds=0.0 if retry_delay_seconds is not None else retry_jitter_seconds,
        )
        self.retry_observer = retry_observer
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
            "response_format": {"type": "json_object"},
        }
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            response = execute_http_request(
                provider="LLM",
                operation="生成",
                policy=self.retry_policy,
                observer=self.retry_observer,
                send=lambda timeout: self._post(
                    endpoint=endpoint,
                    headers=headers,
                    body=body,
                    timeout=timeout,
                ),
            )
        except ProviderRequestError as exc:
            raise ChatProviderError(str(exc)) from exc

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ChatProviderError(
                str(
                    invalid_response_failure(
                        provider="LLM", operation="生成", observer=self.retry_observer
                    )
                )
            ) from exc
        try:
            return _parse_json_object(str(content))
        except ChatProviderError as exc:
            raise ChatProviderError(
                str(
                    invalid_response_failure(
                        provider="LLM", operation="生成", observer=self.retry_observer
                    )
                )
            ) from exc

    def _post(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        if self.client is not None:
            return self.client.post(endpoint, headers=headers, json=body, timeout=timeout)
        with httpx.Client(timeout=timeout) as client:
            return client.post(endpoint, headers=headers, json=body)


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    data = _loads_json_object(stripped)
    if not isinstance(data, dict):
        raise ChatProviderError("Chat completion JSON must be an object.")
    return data


def _loads_json_object(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as original_error:
        candidate = _extract_first_json_object(content)
        if not candidate:
            raise ChatProviderError("Chat completion did not return valid JSON.") from original_error
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ChatProviderError("Chat completion did not return valid JSON.") from exc


def _extract_first_json_object(content: str) -> str:
    start = content.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]
    return ""
