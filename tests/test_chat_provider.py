from __future__ import annotations

import httpx

from domain_atlas.providers.chat import OpenAICompatibleChatProvider


def test_openai_compatible_chat_provider_parses_json_content():
    expected_key = "not-a-real-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example.com/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {expected_key}"
        body = request.read()
        assert b'"response_format":{"type":"json_object"}' in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"ok": true, "items": [1]}\n```'
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleChatProvider(
        api_key=expected_key,
        base_url="https://llm.example.com",
        model="test-chat",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.complete_json(system_prompt="system", user_prompt="user") == {
        "ok": True,
        "items": [1],
    }


def test_chat_provider_extracts_json_object_from_surrounding_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '好的，下面是 JSON：\n{"ok": true, "text": "brace } inside"}\n完成。'
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleChatProvider(
        api_key="not-a-real-key",
        base_url="https://llm.example.com",
        model="test-chat",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.complete_json(system_prompt="system", user_prompt="user") == {
        "ok": True,
        "text": "brace } inside",
    }


def test_chat_provider_retries_transient_overload():
    expected_key = "not-a-real-key"
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                503,
                json={
                    "error": {
                        "message": "Server Overloaded",
                        "code": "service_unavailable_error",
                    }
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    provider = OpenAICompatibleChatProvider(
        api_key=expected_key,
        base_url="https://llm.example.com",
        model="test-chat",
        max_retries=1,
        retry_delay_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.complete_json(system_prompt="system", user_prompt="user") == {"ok": True}
    assert calls["count"] == 2
