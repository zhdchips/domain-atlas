"""Run a fixed live E2E build with configured LLM and embedding providers."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from domain_atlas.core.db import connect
from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.qa import QARepository
from domain_atlas.domain.sources import ChunkRepository, SourceRepository
from domain_atlas.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "live_domain_atlas_seed.md"


def main() -> int:
    _load_env(PROJECT_ROOT / ".env")
    _require_env(
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "CHAT_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
    )

    started = time.monotonic()
    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-live-e2e-"))
    try:
        project_id = _run_live_e2e(workdir)
    except Exception as exc:
        print(f"FAIL live-e2e: {_safe_error(exc)}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    else:
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"PASS live-e2e project_id={project_id} elapsed={time.monotonic() - started:.1f}s")
        return 0


def _run_live_e2e(workdir: Path) -> int:
    data_dir = workdir / "data"
    settings = Settings(data_dir=data_dir)
    client = TestClient(create_app(settings))

    create = client.post(
        "/domains",
        data={
            "name": "Domain Atlas Live Regression",
            "goal": "验证固定资料可生成 LLM Wiki、学习路线和可溯源问答",
            "level": "beginner",
            "language": "zh",
            "interaction_mode": "guided",
        },
        follow_redirects=False,
    )
    _expect_redirect(create, "/domains/")
    project_id = _project_id_from_location(create.headers["location"])
    print(f"created project={project_id}")

    fixture_bytes = FIXTURE_PATH.read_bytes()
    upload = client.post(
        f"/domains/{project_id}/sources/file",
        files={
            "file": (
                FIXTURE_PATH.name,
                fixture_bytes,
                "text/markdown",
            )
        },
        follow_redirects=False,
    )
    _expect_redirect(upload, f"/domains/{project_id}")

    sources = SourceRepository(settings.database_path).list_for_project(project_id)
    if len(sources) != 1:
        raise RuntimeError(f"expected one uploaded source, got {len(sources)}")
    source = sources[0]
    print(f"uploaded source={source.id} title={source.title}")

    ingest = client.post(
        f"/domains/{project_id}/sources/{source.id}/ingest",
        follow_redirects=False,
    )
    _expect_redirect(ingest, f"/domains/{project_id}")
    chunk_count = ChunkRepository(settings.database_path).count_for_project(project_id)
    if chunk_count < 1:
        raise RuntimeError("ingestion produced no chunks")
    print(f"ingested chunks={chunk_count}")

    build = client.post(f"/domains/{project_id}/build", follow_redirects=False)
    _expect_redirect(build, f"/domains/{project_id}")
    project = DomainProjectRepository(settings.database_path).get(project_id)
    if project is None or project.build_status != "completed":
        raise RuntimeError(f"project build_status was {project.build_status if project else 'missing'}")

    artifacts = KnowledgeArtifactRepository(settings.database_path)
    pages = artifacts.list_wiki_pages(project_id)
    sections = artifacts.list_wiki_sections(project_id)
    modules = artifacts.list_learning_modules(project_id)
    concept_count = _count_rows(settings.database_path, "concepts", project_id)
    paths = {page.path for page in pages}
    required_paths = {"wiki/index", "wiki/log", "wiki/synthesis/overview", "wiki/templates/source", "wiki/templates/concept"}
    missing_paths = sorted(required_paths - paths)
    if missing_paths:
        raise RuntimeError(f"missing required wiki paths: {missing_paths}")
    if not any(page.page_type == "source" for page in pages):
        raise RuntimeError("build did not create source pages")
    if not any(page.page_type == "concept" for page in pages):
        raise RuntimeError("build did not create concept pages")
    if len(sections) <= 8:
        raise RuntimeError(f"expected more than 8 wiki sections to exercise embedding batching, got {len(sections)}")
    if len(modules) != 5:
        raise RuntimeError(f"expected 5 learning modules, got {len(modules)}")
    if concept_count < 6:
        raise RuntimeError(f"expected at least 6 concepts, got {concept_count}")
    print(
        "built artifacts "
        f"pages={len(pages)} sections={len(sections)} modules={len(modules)} concepts={concept_count}"
    )

    for route in ("wiki", "path", "qa"):
        response = client.get(f"/domains/{project_id}/{route}")
        if response.status_code != 200:
            raise RuntimeError(f"GET /domains/{project_id}/{route} returned HTTP {response.status_code}")
    print("verified wiki/path/qa pages")

    ask = client.post(
        f"/domains/{project_id}/qa",
        data={"question": "Domain Atlas 为什么需要 citation 和 provenance？"},
        follow_redirects=False,
    )
    _expect_redirect(ask, f"/domains/{project_id}/qa")
    records = QARepository(settings.database_path).list_for_project(project_id)
    if not records:
        raise RuntimeError("QA did not create a record")
    latest = records[0]
    if latest.evidence_status != "sufficient" or not latest.answer or not latest.citations:
        raise RuntimeError(
            "QA did not return a sufficient cited answer: "
            f"status={latest.evidence_status} citations={latest.citations}"
        )
    print(f"verified qa citations={latest.citations}")
    return project_id


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _require_env(*names: str) -> None:
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(f"missing required live E2E environment variables: {', '.join(missing)}")


def _expect_redirect(response, expected_prefix: str) -> None:
    if response.status_code != 303:
        raise RuntimeError(
            f"expected HTTP 303, got HTTP {response.status_code}: {response.text[:500]}"
        )
    location = response.headers.get("location", "")
    if not location.startswith(expected_prefix):
        raise RuntimeError(f"expected redirect to {expected_prefix}, got {location}")


def _project_id_from_location(location: str) -> int:
    try:
        return int(location.rstrip("/").split("/")[-1])
    except ValueError as exc:
        raise RuntimeError(f"could not parse project id from location: {location}") from exc


def _count_rows(database_path: Path, table: str, project_id: int) -> int:
    if table not in {"concepts"}:
        raise ValueError(f"Unsupported count table: {table}")
    with connect(database_path) as connection:
        row = connection.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return int(row["count"])


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("EXA_API_KEY", "LLM_API_KEY", "EMBEDDING_API_KEY", "DASHSCOPE_API_KEY"):
        secret = os.environ.get(key, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


if __name__ == "__main__":
    sys.exit(main())
