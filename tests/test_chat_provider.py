from __future__ import annotations

import httpx

from domain_atlas.providers.chat import OpenAICompatibleChatProvider


def test_openai_compatible_chat_provider_parses_json_content():
    expected_key = "not-a-real-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example.com/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {expected_key}"
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
