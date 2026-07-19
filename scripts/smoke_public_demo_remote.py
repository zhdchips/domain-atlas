"""Verify a deployed public Demo without sending provider-backed requests."""

from __future__ import annotations

import argparse
import sys
import time
from urllib.parse import urlsplit, urlunsplit

import httpx


DEMO_PAGES = {
    "/demo": ("Agent Harness Engineering", "OpenAI Agents SDK documentation"),
    "/demo/wiki": ("Harness Map", 'href="/demo/wiki/concepts/agent-loop"'),
    "/demo/wiki/concepts/agent-loop": ("Agent Loop", "引用与来源"),
    "/demo/path": ("从主干到支线逐步推进", 'href="/demo/wiki/concepts/agent-loop"'),
    "/demo/qa": ("为什么 Agent Harness 不等于一个更长的 prompt？", 'href="/demo/wiki/concepts/agent-loop"'),
    "/demo/evaluation": ("25 / 25", "固定 Demo catalog"),
}
BLOCKED_GET_PATHS = ("/domains", "/domains/1", "/docs", "/openapi.json")
BLOCKED_POST_PATHS = (
    "/demo",
    "/domains",
    "/domains/1/discover",
    "/domains/1/sources/url",
    "/domains/1/sources/file",
    "/domains/1/build",
    "/domains/1/autopilot",
    "/domains/1/qa",
)
EXTERNAL_CITATION = 'href="https://openai.github.io/openai-agents-python/#why-use-the-agents-sdk"'


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check a read-only Domain Atlas Demo.")
    parser.add_argument("--base-url", required=True, help="Demo origin, for example http://127.0.0.1:8000")
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=90.0,
        help="Total seconds allowed for a sleeping service to become healthy.",
    )
    parser.add_argument("--request-timeout", type=float, default=10.0)
    args = parser.parse_args()

    try:
        base_url = normalize_base_url(args.base_url)
        verify_public_demo(
            base_url,
            startup_timeout=args.startup_timeout,
            request_timeout=args.request_timeout,
        )
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        print(f"FAIL public-demo remote smoke: {exc}")
        return 1

    print(f"PASS public-demo remote smoke: {base_url}")
    return 0


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base URL must be an absolute HTTP or HTTPS origin")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a path, query, or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def verify_public_demo(base_url: str, *, startup_timeout: float, request_timeout: float) -> None:
    if startup_timeout <= 0 or request_timeout <= 0:
        raise ValueError("timeouts must be positive")

    headers = {"User-Agent": "domain-atlas-public-demo-smoke/1.0"}
    with httpx.Client(headers=headers, follow_redirects=False, timeout=request_timeout) as client:
        health = wait_for_health(client, base_url, startup_timeout=startup_timeout)
        payload = health.json()
        if payload.get("status") != "ok" or payload.get("app") != "Domain Atlas":
            raise RuntimeError(f"unexpected health payload: {payload}")

        root = client.get(f"{base_url}/")
        expect_status(root, 307, "root redirect")
        if root.headers.get("location") != "/demo":
            raise RuntimeError(f"root redirected to {root.headers.get('location')!r}, expected '/demo'")

        page_bodies: dict[str, str] = {}
        for path, markers in DEMO_PAGES.items():
            response = client.get(f"{base_url}{path}")
            expect_status(response, 200, path)
            for marker in markers:
                if marker not in response.text:
                    raise RuntimeError(f"{path} is missing marker {marker!r}")
            page_bodies[path] = response.text

        if EXTERNAL_CITATION not in page_bodies["/demo/wiki"]:
            raise RuntimeError("Wiki source citation is missing or is not an HTTPS link")

        for path in BLOCKED_GET_PATHS:
            expect_status(client.get(f"{base_url}{path}"), 404, f"blocked GET {path}")

        for path in BLOCKED_POST_PATHS:
            expect_status(client.post(f"{base_url}{path}"), 404, f"blocked POST {path}")


def wait_for_health(client: httpx.Client, base_url: str, *, startup_timeout: float) -> httpx.Response:
    deadline = time.monotonic() + startup_timeout
    last_detail = "no response"
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{base_url}/health")
            if response.status_code == 200:
                return response
            last_detail = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_detail = str(exc)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(2.0, remaining))
    raise RuntimeError(f"service did not become healthy within {startup_timeout:g}s ({last_detail})")


def expect_status(response: httpx.Response, expected: int, label: str) -> None:
    if response.status_code != expected:
        raise RuntimeError(f"{label} returned HTTP {response.status_code}, expected {expected}")


if __name__ == "__main__":
    sys.exit(main())
