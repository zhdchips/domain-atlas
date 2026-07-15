"""Run Playwright checks for the Wiki workspace layout."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("FAIL browser-e2e: playwright is not installed.")
        print("Run: uv sync --extra dev && uv run python -m playwright install chromium")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-browser-e2e-"))
    server: subprocess.Popen[str] | None = None
    try:
        data_dir = workdir / "data"
        settings = Settings(data_dir=data_dir)
        project_id = _create_wiki_fixture(settings)
        port = _free_port()
        server = _start_server(data_dir=data_dir, port=port)
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base_url}/domains/{project_id}/wiki/index", wait_until="networkidle")
            page.locator(".wiki-workspace").wait_for(state="visible", timeout=5000)
            _assert_wiki_layout(page)
            browser.close()
    except PlaywrightError as exc:
        print(f"FAIL browser-e2e: Playwright could not run Chromium: {exc}")
        print("Run: uv run python -m playwright install chromium")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    except Exception as exc:
        print(f"FAIL browser-e2e: {exc}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    finally:
        if server is not None:
            _stop_server(server)

    shutil.rmtree(workdir, ignore_errors=True)
    print("PASS browser-e2e wiki layout")
    return 0


def _create_wiki_fixture(settings: Settings) -> int:
    initialize_database(settings.database_path)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(
            name="Browser Layout Regression",
            goal="Validate Wiki workspace rendering.",
            language="zh",
        )
    )
    KnowledgeArtifactRepository(settings.database_path).replace_project_artifacts(
        project.id,
        {
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [],
            "wiki_pages": [
                _page("index", "wiki/index", "Wiki Index", "Wiki 工作区的中心目录。"),
                _page("log", "wiki/log", "Wiki Log", "Wiki 工作区的构建日志。"),
                _page(
                    "source",
                    "wiki/sources/domain-atlas-source",
                    "Domain Atlas Source",
                    "固定资料摘要。",
                ),
                _page("concept", "wiki/concepts/provenance", "Provenance", "可溯源能力。"),
                _page("concept", "wiki/concepts/wiki-section", "WikiSection", "可检索段落。"),
                _page("entity", "wiki/entities/domain-atlas", "Domain Atlas", "领域学习系统。"),
                _page("synthesis", "wiki/synthesis/overview", "综合页", "跨页面综合。"),
                _page("template", "wiki/templates/source", "资料页模板", "资料页结构模板。"),
                _page("template", "wiki/templates/concept", "概念页模板", "概念页结构模板。"),
            ],
        },
    )
    return project.id


def _page(page_type: str, path: str, title: str, summary: str) -> dict[str, Any]:
    slug = path.rstrip("/").split("/")[-1]
    return {
        "slug": slug,
        "page_type": page_type,
        "path": path,
        "title": title,
        "topic_path": path.removeprefix("wiki/"),
        "summary": summary,
        "body_markdown": f"# {title}\n\n{summary}\n\n- [[Provenance]]\n- [[WikiSection]]",
        "citations": ["S1-C1"] if page_type in {"source", "concept", "entity", "synthesis"} else [],
        "sections": [
            {
                "section_uid": f"{slug}#1",
                "heading": title,
                "body_markdown": summary,
                "citations": [f"W:{slug}#1"],
                "source_citation_labels": ["S1-C1"],
                "source_chunk_uids": ["chunk:layout:1"],
                "links": ["Provenance", "WikiSection"],
            }
        ],
    }


def _start_server(*, data_dir: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
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
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
    raise RuntimeError("server did not become healthy")


def _assert_wiki_layout(page) -> None:
    metrics = page.evaluate(
        """
        () => {
          const workspace = document.querySelector(".wiki-workspace");
          const tree = document.querySelector(".wiki-tree");
          const article = document.querySelector(".wiki-page");
          const stylesheet = document.querySelector('link[href*="styles.css?v="]');
          const treeBox = tree.getBoundingClientRect();
          const articleBox = article.getBoundingClientRect();
          return {
            stylesheetHref: stylesheet ? stylesheet.href : "",
            workspaceDisplay: getComputedStyle(workspace).display,
            workspaceColumns: getComputedStyle(workspace).gridTemplateColumns,
            treeX: treeBox.x,
            treeWidth: treeBox.width,
            articleX: articleBox.x,
            articleWidth: articleBox.width,
            articleTop: articleBox.y,
            linkCount: document.querySelectorAll(".wiki-tree-link").length,
            activeText: document.querySelector(".wiki-tree-link.active")?.textContent || "",
          };
        }
        """
    )
    failures: list[str] = []
    if "styles.css?v=" not in metrics["stylesheetHref"]:
        failures.append("stylesheet version parameter is missing")
    if metrics["workspaceDisplay"] != "grid":
        failures.append(f"workspace display is {metrics['workspaceDisplay']!r}, expected 'grid'")
    if metrics["treeWidth"] < 280:
        failures.append(f"wiki tree width is too small: {metrics['treeWidth']:.1f}")
    if metrics["articleWidth"] < 600:
        failures.append(f"wiki article width is too small: {metrics['articleWidth']:.1f}")
    if metrics["articleX"] <= metrics["treeX"] + metrics["treeWidth"] + 12:
        failures.append(
            "wiki article is not laid out to the right of the tree: "
            f"treeX={metrics['treeX']:.1f} treeWidth={metrics['treeWidth']:.1f} "
            f"articleX={metrics['articleX']:.1f}"
        )
    if metrics["linkCount"] < 8:
        failures.append(f"expected at least 8 tree links, got {metrics['linkCount']}")
    if "Wiki Index" not in metrics["activeText"]:
        failures.append(f"active tree link did not select Wiki Index: {metrics['activeText']!r}")
    if failures:
        raise RuntimeError("; ".join(failures))
    print(
        "verified wiki layout "
        f"columns={metrics['workspaceColumns']} "
        f"tree={metrics['treeWidth']:.0f}px article={metrics['articleWidth']:.0f}px"
    )


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
