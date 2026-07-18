"""Run one isolated live guided-domain build against configured providers."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.qa import QARepository
from domain_atlas.domain.sources import SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    _load_env(PROJECT_ROOT / ".env")
    _require_env(
        "EXA_API_KEY",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "CHAT_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
    )

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-live-guided-e2e-"))
    started = time.monotonic()
    try:
        outcome = _run_live_guided_e2e(workdir)
    except Exception as exc:
        print(f"FAIL live-guided-e2e: {_safe_error(exc)}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    else:
        shutil.rmtree(workdir, ignore_errors=True)
        print(
            "PASS live-guided-e2e "
            f"project_id={outcome['project_id']} candidates={outcome['candidate_count']} "
            f"attempted={outcome['attempted_count']} successful_sources={outcome['success_count']} "
            f"elapsed={time.monotonic() - started:.1f}s"
        )
        return 0


def _run_live_guided_e2e(workdir: Path) -> dict[str, int]:
    query = os.environ.get("LIVE_GUIDED_E2E_QUERY", "OpenAI Agents SDK official documentation").strip()
    if not query:
        raise RuntimeError("LIVE_GUIDED_E2E_QUERY must not be blank.")
    settings = Settings(
        data_dir=workdir / "data",
        INTAKE_LLM_ASSESSMENT_ENABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(
            name=query,
            scope=query,
            goal="验证真实搜索、资料摄取、领域 Wiki 和可溯源问答。",
            level="beginner",
            language="zh",
            interaction_mode="guided",
        )
    )
    print(f"created project={project.id} query={query!r}")

    response = client.post(f"/domains/{project.id}/autopilot", follow_redirects=False)
    if response.status_code != 303:
        raise RuntimeError(f"guided start returned HTTP {response.status_code}: {response.text[:500]}")
    _wait_for_workflow(
        WorkflowRepository(settings.database_path),
        project_id=project.id,
        workflow_name="guided_autopilot",
        timeout_seconds=720,
    )
    runs = WorkflowRepository(settings.database_path).list_for_project(project.id, limit=10)
    run = next((item for item in runs if item.workflow_name == "guided_autopilot"), None)
    if run is None:
        raise RuntimeError("guided workflow record was not found after completion")
    ingestion_step = next(
        (
            step
            for step in reversed(run.steps)
            if step.step_name == "ingest_sources" and step.status in {"completed", "failed"}
        ),
        None,
    )
    if ingestion_step is None:
        selection_step = next(
            (
                step
                for step in reversed(run.steps)
                if step.step_name == "select_candidates" and step.status == "failed"
            ),
            None,
        )
        if selection_step is not None:
            raise RuntimeError(
                "guided selection stopped with "
                f"{selection_step.output.get('terminal_reason', 'unknown')}: "
                f"{selection_step.output.get('recovery_message', run.error)}"
            )
        raise RuntimeError("guided workflow did not persist an ingestion summary")
    summary = ingestion_step.output
    candidate_count = int(
        next(
            (
                step.output.get("candidate_count", 0)
                for step in run.steps
                if step.step_name == "discover_candidates" and step.status == "completed"
            ),
            0,
        )
    )
    attempted_count = int(summary.get("attempted_count", 0))
    success_count = int(summary.get("success_count", 0))
    print(
        "guided ingestion "
        f"terminal_reason={summary.get('terminal_reason', '')} attempted={attempted_count} "
        f"successful_sources={success_count} independent_families="
        f"{len(summary.get('successful_families', []))} failed={summary.get('failed_count', 0)}"
    )
    if run.status != "completed":
        raise RuntimeError(
            f"guided workflow ended with {run.status}: {run.error or summary.get('recovery_message', '')}"
        )
    if success_count < 2:
        raise RuntimeError(f"guided workflow completed below the two-source gate: {success_count}")
    if len(summary.get("successful_families", [])) < 2:
        raise RuntimeError("guided workflow completed below the independent-source-family gate")

    project_after = DomainProjectRepository(settings.database_path).get(project.id)
    if project_after is None or project_after.build_status != "completed":
        raise RuntimeError("guided workflow did not complete the knowledge build")
    sources = [
        source
        for source in SourceRepository(settings.database_path).list_for_project(project.id)
        if source.status == "ingested"
    ]
    if len(sources) < 2:
        raise RuntimeError(f"expected two ingested sources, got {len(sources)}")
    pages = KnowledgeArtifactRepository(settings.database_path).list_wiki_pages(project.id)
    if not pages:
        raise RuntimeError("guided workflow did not create Wiki pages")

    question = f"{query} 的核心作用是什么？"
    qa = client.post(
        f"/domains/{project.id}/qa",
        data={"question": question},
        follow_redirects=False,
    )
    if qa.status_code != 303:
        raise RuntimeError(f"guided QA returned HTTP {qa.status_code}: {qa.text[:500]}")
    records = QARepository(settings.database_path).list_for_project(project.id)
    if not records or records[0].evidence_status != "sufficient" or not records[0].citations:
        raise RuntimeError("guided QA did not return a sufficient cited answer")
    print(f"verified wiki pages={len(pages)} qa_citations={records[0].citations}")
    return {
        "project_id": project.id,
        "candidate_count": candidate_count,
        "attempted_count": attempted_count,
        "success_count": success_count,
    }


def _wait_for_workflow(
    repository: WorkflowRepository,
    *,
    project_id: int,
    workflow_name: str,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        runs = repository.list_for_project(project_id, limit=10)
        matching = next((run for run in runs if run.workflow_name == workflow_name), None)
        if matching is not None and matching.status not in {"queued", "running"}:
            return
        time.sleep(0.5)
    raise RuntimeError(f"{workflow_name} did not finish within {timeout_seconds:.0f}s")


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
        raise RuntimeError(f"missing required live guided E2E environment variables: {', '.join(missing)}")


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("EXA_API_KEY", "LLM_API_KEY", "EMBEDDING_API_KEY", "DASHSCOPE_API_KEY"):
        secret = os.environ.get(key, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


if __name__ == "__main__":
    sys.exit(main())
