"""Smoke test configured live providers without printing secrets."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import certifi
import httpx


def main() -> int:
    env = _load_env(Path(".env"))
    checks = [
        ("search", _check_search),
        ("chat", _check_chat),
        ("embedding", _check_embedding),
    ]
    failed = False
    with httpx.Client(timeout=45.0, verify=certifi.where()) as client:
        for name, check in checks:
            start = time.monotonic()
            try:
                check(env, client)
            except Exception as exc:
                failed = True
                print(f"FAIL {name}: {_safe_error(exc)}")
            finally:
                print(f"elapsed {name}={time.monotonic() - start:.1f}s")
    return 1 if failed else 0


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(".env is missing")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env[key] = value
        os.environ[key] = value
    return env


def _check_search(env: dict[str, str], client: httpx.Client) -> None:
    key = env.get("EXA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EXA_API_KEY is missing")
    response = client.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": key},
        json={
            "query": "Domain Atlas knowledge wiki learning path",
            "numResults": 1,
            "contents": {"summary": True, "highlights": True},
        },
    )
    _raise_for_status(response)
    results = response.json().get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError("Exa returned no usable results")
    print(f"PASS search provider=exa results={len(results)}")


def _check_chat(env: dict[str, str], client: httpx.Client) -> None:
    key = env.get("LLM_API_KEY", "").strip()
    base_url = env.get("LLM_BASE_URL", "").strip().rstrip("/")
    model = env.get("CHAT_MODEL", "").strip()
    if not key or not base_url or not model:
        raise RuntimeError("LLM_API_KEY, LLM_BASE_URL, or CHAT_MODEL is missing")
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    response = client.post(
        endpoint,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "temperature": 0,
            "max_tokens": 8,
        },
    )
    _raise_for_status(response)
    content = response.json()["choices"][0]["message"]["content"]
    if not content:
        raise RuntimeError("Chat provider returned empty content")
    print(f"PASS chat model={model}")


def _check_embedding(env: dict[str, str], client: httpx.Client) -> None:
    key = (env.get("EMBEDDING_API_KEY") or env.get("DASHSCOPE_API_KEY") or "").strip()
    base_url = env.get("EMBEDDING_BASE_URL", "").strip().rstrip("/")
    model = env.get("EMBEDDING_MODEL", "").strip()
    dimensions = env.get("EMBEDDING_DIMENSIONS", "").strip()
    if not key or not base_url or not model:
        raise RuntimeError("EMBEDDING_API_KEY, EMBEDDING_BASE_URL, or EMBEDDING_MODEL is missing")
    body: dict[str, object] = {"model": model, "input": "Domain Atlas embedding smoke test"}
    if dimensions:
        body["dimensions"] = int(dimensions)
    response = client.post(
        f"{base_url}/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
    )
    _raise_for_status(response)
    data = response.json().get("data")
    vector = data[0].get("embedding") if isinstance(data, list) and data else None
    if not isinstance(vector, list) or not vector:
        raise RuntimeError("Embedding provider returned no vector")
    print(f"PASS embedding model={model} dimensions={len(vector)}")


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        try:
            payload = response.json()
            body = json.dumps(payload, ensure_ascii=False)[:300]
        except Exception:
            body = response.text[:300]
        raise RuntimeError(f"HTTP {response.status_code}: {body}")


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("EXA_API_KEY", "LLM_API_KEY", "EMBEDDING_API_KEY"):
        text = text.replace(os.environ.get(key, ""), "[redacted]") if os.environ.get(key) else text
    return text


if __name__ == "__main__":
    sys.exit(main())
