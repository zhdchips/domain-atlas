from __future__ import annotations

import httpx

from domain_atlas.core.resilience import RetryPolicy, execute_http_request


def test_shared_policy_uses_bounded_exponential_backoff_jitter_and_recovery_event():
    responses = [httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"ok": True})]
    events = []
    delays = []
    timeouts = []

    def send(timeout: float) -> httpx.Response:
        timeouts.append(timeout)
        return responses.pop(0)

    response = execute_http_request(
        provider="Test",
        operation="读取",
        policy=RetryPolicy(
            timeout_seconds=12,
            max_retries=2,
            base_delay_seconds=1,
            jitter_seconds=0.25,
        ),
        send=send,
        observer=events.append,
        sleep=delays.append,
        random_uniform=lambda _minimum, _maximum: 0.1,
    )

    assert response.status_code == 200
    assert timeouts == [12, 12, 12]
    assert delays == [1.1, 2.1]
    assert [event.phase for event in events] == ["retrying", "retrying", "recovered"]
    assert events[0].failure.category == "server_error"
    assert events[1].failure.category == "rate_limited"
    assert events[-1].failure.attempts == 2
