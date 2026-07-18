"""Run Playwright checks for the anonymous read-only public Demo surface."""

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


def main() -> int:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("FAIL browser-e2e public-demo: playwright is not installed.")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-public-demo-e2e-"))
    data_dir = workdir / "absent-data"
    server: subprocess.Popen[str] | None = None
    try:
        port = _free_port()
        server = _start_server(data_dir=data_dir, port=port)
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url)
        if data_dir.exists():
            raise RuntimeError("public demo created a runtime data directory")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base_url}/demo", wait_until="networkidle")
            if "Agent Harness Engineering" not in page.locator("body").inner_text():
                raise RuntimeError("public demo overview content is missing")
            if page.locator("form").count() or page.locator('button[type="submit"]').count():
                raise RuntimeError("public demo exposed a mutable form or submit button")
            page.get_by_role("link", name="LLM Wiki").click()
            page.wait_for_url("**/demo/wiki", timeout=5000)
            if "Harness Map" not in page.locator("body").inner_text():
                raise RuntimeError("public demo Wiki content is missing")
            page.goto(f"{base_url}/demo/path", wait_until="networkidle")
            if "从主干到支线逐步推进" not in page.locator("body").inner_text():
                raise RuntimeError("public demo learning path is missing")
            page.goto(f"{base_url}/demo/qa", wait_until="networkidle")
            if "为什么 Agent Harness 不等于一个更长的 prompt？" not in page.locator("body").inner_text():
                raise RuntimeError("public demo cited QA examples are missing")
            if page.locator("form").count() or page.locator('button[type="submit"]').count():
                raise RuntimeError("public demo QA exposed a mutable form or submit button")
            browser.close()

        with httpx.Client(base_url=base_url, timeout=5) as client:
            for path in ("/domains", "/domains/1/autopilot", "/domains/1/qa", "/demo"):
                response = client.post(path)
                if response.status_code != 404:
                    raise RuntimeError(f"public demo mutation path {path} returned {response.status_code}")
    except PlaywrightError as exc:
        print(f"FAIL browser-e2e public-demo: Playwright could not run Chromium: {exc}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    except Exception as exc:
        print(f"FAIL browser-e2e public-demo: {exc}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    finally:
        if server is not None:
            _stop_server(server)

    shutil.rmtree(workdir, ignore_errors=True)
    print("PASS browser-e2e public read-only demo")
    return 0


def _start_server(*, data_dir: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["PUBLIC_DEMO_MODE"] = "true"
    env["INTAKE_LLM_ASSESSMENT_ENABLED"] = "false"
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
    raise RuntimeError("public demo server did not become healthy")


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
