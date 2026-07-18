"""Capture deterministic public-Demo screenshots used by the repository README."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "docs" / "assets"
PAGES = {
    "demo-overview.png": "/demo",
    "demo-wiki.png": "/demo/wiki",
    "demo-learning-path.png": "/demo/path",
    "demo-cited-qa.png": "/demo/qa",
}


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("Playwright is required. Run: uv sync --extra dev && uv run python -m playwright install chromium")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-release-screenshots-"))
    server: subprocess.Popen[str] | None = None
    try:
        port = _free_port()
        server = _start_server(workdir / "absent-data", port)
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url)
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            for filename, path in PAGES.items():
                page.goto(f"{base_url}{path}", wait_until="networkidle")
                page.screenshot(path=str(ASSET_DIR / filename), full_page=True)
                print(f"captured docs/assets/{filename}")
            browser.close()
    finally:
        if server is not None:
            _stop_server(server)
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


def _start_server(data_dir: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(
        {
            "DATA_DIR": str(data_dir),
            "PUBLIC_DEMO_MODE": "true",
            "INTAKE_LLM_ASSESSMENT_ENABLED": "false",
        }
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "domain_atlas.web.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + 20
    with httpx.Client(timeout=1.0) as client:
        while time.monotonic() < deadline:
            try:
                if client.get(f"{base_url}/health").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
    raise RuntimeError("public Demo server did not become healthy")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stop_server(server: subprocess.Popen[str]) -> None:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
