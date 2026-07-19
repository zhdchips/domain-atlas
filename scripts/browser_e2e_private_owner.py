"""Playwright regression for private owner login and mobile learning workflows."""

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
        print("FAIL browser-e2e private-owner: playwright is not installed.")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-private-owner-e2e-"))
    server: subprocess.Popen[str] | None = None
    try:
        data_dir = (workdir / "persistent-data").resolve()
        port = _free_port()
        server = _start_server(data_dir=data_dir, port=port)
        base_url = f"http://localhost:{port}"
        _wait_for_health(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(base_url, wait_until="networkidle")
            if page.url != f"{base_url}/auth/sign-in?next=%2F":
                raise RuntimeError(f"private root did not require sign-in: {page.url}")
            if "使用 GitHub 登录" not in page.locator("body").inner_text():
                raise RuntimeError("GitHub owner login entry is missing")
            page.get_by_role("link", name="使用 GitHub 登录").click()
            page.wait_for_url(f"{base_url}/", timeout=5000)
            if "Browser Layout Regression" not in page.locator("body").inner_text():
                raise RuntimeError("owner session did not reach the private project list")

            page.get_by_label("领域名称").fill("Mobile Learning Atlas")
            page.get_by_role("button", name="创建项目").click()
            page.wait_for_url(f"{base_url}/domains/7", timeout=5000)
            if "Mobile Learning Atlas" not in page.locator("h1").inner_text():
                raise RuntimeError("private project creation did not reach its dashboard")

            page.goto(f"{base_url}/domains/1", wait_until="networkidle")
            page.get_by_role("button", name="一键构建领域地图").click()
            page.locator(".workflow-run-active").wait_for(state="visible", timeout=3000)
            page.locator(".workflow-run .status-completed").first.wait_for(
                state="visible", timeout=7000
            )

            expected_content = {
                "/domains/1/wiki/index": "Wiki Index",
                "/domains/1/path": "领域主线",
                "/domains/1/qa": "私有知识库如何保持可溯源",
            }
            for path, text in expected_content.items():
                page.goto(f"{base_url}{path}", wait_until="networkidle")
                if text not in page.locator("body").inner_text():
                    raise RuntimeError(f"private learning page is incomplete: {path}")

            page.set_viewport_size({"width": 390, "height": 844})
            for path in (
                "/",
                "/domains/1",
                "/domains/1/wiki/index",
                "/domains/1/path",
                "/domains/1/qa",
            ):
                page.goto(f"{base_url}{path}", wait_until="networkidle")
                _assert_mobile_page(page, path=path)
            page.get_by_role("link", name="Domain Atlas").click()
            page.wait_for_url(f"{base_url}/", timeout=5000)
            page.get_by_role("button", name="退出").click()
            page.wait_for_url(f"{base_url}/auth/sign-in", timeout=5000)
            _assert_mobile_page(page, path="/auth/sign-in")
            browser.close()
    except PlaywrightError as exc:
        print(f"FAIL browser-e2e private-owner: Playwright could not run Chromium: {exc}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    except Exception as exc:
        print(f"FAIL browser-e2e private-owner: {exc}")
        if server is not None and server.stdout is not None:
            server.terminate()
            try:
                output, _ = server.communicate(timeout=3)
                print(output[-4000:])
            except subprocess.TimeoutExpired:
                pass
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    finally:
        if server is not None and server.poll() is None:
            _stop_server(server)

    shutil.rmtree(workdir, ignore_errors=True)
    print("PASS browser-e2e private owner desktop and mobile workflows")
    return 0


def _assert_mobile_page(page, *, path: str) -> None:
    dimensions = page.evaluate(
        "() => ({ viewport: window.innerWidth, documentWidth: document.documentElement.scrollWidth })"
    )
    if dimensions["documentWidth"] > dimensions["viewport"] + 1:
        raise RuntimeError(f"private page overflows on mobile {path}: {dimensions}")
    if not page.locator(".topbar").is_visible():
        raise RuntimeError(f"private page navigation is hidden on mobile: {path}")
    for element in page.locator("button:visible, .primary-link:visible").all():
        box = element.bounding_box()
        if box is None or box["x"] < -1 or box["x"] + box["width"] > 391:
            raise RuntimeError(f"private page control is outside the mobile viewport: {path}")


def _start_server(*, data_dir: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(
        {
            "DATA_DIR": str(data_dir),
            "DEPLOYMENT_MODE": "private_owner",
            "PUBLIC_DEMO_MODE": "false",
            "PERSISTENT_DATA_ACKNOWLEDGED": "true",
            "GITHUB_OAUTH_CLIENT_ID": "browser-client",
            "GITHUB_OAUTH_CLIENT_SECRET": "browser-secret",
            "GITHUB_OAUTH_CALLBACK_URL": f"http://localhost:{port}/auth/callback",
            "OWNER_GITHUB_USER_ID": "4242",
            "SESSION_SECRET": "browser-session-secret-that-is-long-enough-1234",
            "SESSION_COOKIE_SECURE": "true",
            "INTAKE_LLM_ASSESSMENT_ENABLED": "false",
        }
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.browser_e2e_private_fixture_app:create_app",
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
    raise RuntimeError("private owner fixture server did not become healthy")


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
