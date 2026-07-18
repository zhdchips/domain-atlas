from __future__ import annotations

import json

from domain_atlas.core.db import connect, initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateDraft, SourceCandidateRepository
from domain_atlas.domain.sources import SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.workflow.autopilot import AutopilotWorkflow, select_autopilot_candidates


class FakeDiscoveryProvider:
    def __init__(self, drafts: list[SourceCandidateDraft]) -> None:
        self.drafts = drafts
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        self.calls.append((query, limit))
        return self.drafts


class FakeIngestionRunner:
    def __init__(self) -> None:
        self.source_ids: list[int] = []

    def ingest_source(self, source_id: int):
        self.source_ids.append(source_id)


class PartiallyFailingIngestionRunner:
    def __init__(self, failing_source_ids: set[int]) -> None:
        self.failing_source_ids = failing_source_ids
        self.source_ids: list[int] = []

    def ingest_source(self, source_id: int):
        if source_id in self.failing_source_ids:
            raise ValueError("URL fetch failed.")
        self.source_ids.append(source_id)


class FakeBuildRunner:
    def __init__(self) -> None:
        self.project_ids: list[int] = []

    def run(self, project_id: int):
        self.project_ids.append(project_id)


def test_autopilot_candidate_selection_prefers_authoritative_sources():
    drafts = [
        _draft("official-1", "https://docs.example.com/a", "official_docs", 0.9),
        _draft("official-2", "https://docs.example.com/b", "official_docs", 0.88),
        _draft("official-3", "https://docs.example.com/c", "official_docs", 0.87),
        _draft("paper", "https://arxiv.org/abs/1234", "paper", 0.85),
        _draft("blog", "https://blog.example.com/post", "web", 0.99),
        _draft("weak", "https://weak.example.com", "institution", 0.64),
    ]

    selected = select_autopilot_candidates(drafts, max_sources=5)

    assert [candidate.provider_source_id for candidate in selected] == [
        "official-1",
        "official-2",
        "paper",
        "weak",
        "blog",
    ]


def test_autopilot_candidate_selection_adds_fallbacks_when_strict_set_is_small():
    drafts = [
        _draft("encyclopedia", "https://encyclopedia.example.com/agent", "encyclopedia", 0.8),
        _draft("official", "https://docs.example.com/agent", "official_docs", 0.75),
        _draft("practical-a", "https://practical.example.com/a", "web", 0.5),
        _draft("practical-b", "https://practical.example.com/b", "web", 0.5),
    ]

    selected = select_autopilot_candidates(drafts, max_sources=5)

    assert [candidate.provider_source_id for candidate in selected] == [
        "encyclopedia",
        "official",
        "practical-a",
        "practical-b",
    ]


def test_autopilot_candidate_selection_falls_back_to_best_available_web_sources():
    drafts = [
        _draft("creator-a", "https://creator.example.com/a", "web", 0.5),
        _draft("creator-b", "https://creator.example.com/b", "web", 0.5),
        _draft("creator-c", "https://creator.example.com/c", "web", 0.5),
        _draft("media", "https://media.example.com/start", "web", 0.5),
        _draft("weak", "https://weak.example.com/start", "web", 0.49),
    ]

    selected = select_autopilot_candidates(drafts, max_sources=5)

    assert [candidate.provider_source_id for candidate in selected] == [
        "creator-a",
        "creator-b",
        "media",
    ]


def test_autopilot_workflow_creates_sources_ingests_and_builds(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="agent", scope="旅行代理", interaction_mode="guided")
    )
    drafts = [
        _draft("official", "https://docs.example.com/agents", "official_docs", 0.91),
        _draft("paper", "https://arxiv.org/abs/2501.12345", "paper", 0.86),
        _draft("blog", "https://blog.example.com/agents", "web", 0.49),
    ]
    discovery = FakeDiscoveryProvider(drafts)
    ingestion = FakeIngestionRunner()
    build = FakeBuildRunner()

    result = AutopilotWorkflow(
        database_path=database_path,
        discovery_provider=discovery,
        ingestion_runner=ingestion,
        build_runner=build,
        search_limit=12,
    ).run(project.id)

    assert discovery.calls == [("旅行代理", 12)]
    assert result.selected_count == 2
    assert ingestion.source_ids == result.source_ids
    assert build.project_ids == [project.id]

    candidates = SourceCandidateRepository(database_path).list_for_project(project.id)
    accepted = [candidate for candidate in candidates if candidate.status == "accepted"]
    assert [candidate.provider_source_id for candidate in accepted] == ["official", "paper"]

    sources = SourceRepository(database_path).list_for_project(project.id)
    assert {source.locator for source in sources} == {
        "https://docs.example.com/agents",
        "https://arxiv.org/abs/2501.12345",
    }
    assert all(source.metadata["auto_accepted"] is True for source in sources)

    with connect(database_path) as connection:
        run = connection.execute("SELECT * FROM workflow_runs").fetchone()
        steps = connection.execute(
            "SELECT * FROM workflow_steps ORDER BY id ASC"
        ).fetchall()
    assert run["workflow_name"] == "guided_autopilot"
    assert run["status"] == "completed"
    assert [step["step_name"] for step in steps] == [
        "discover_candidates",
        "discover_candidates",
        "select_candidates",
        "select_candidates",
        "ingest_sources",
        "ingest_sources",
        "ingest_sources",
        "ingest_sources",
        "build_knowledge",
        "build_knowledge",
    ]
    assert json.loads(steps[3]["output_json"])["selected_count"] == 2
    assert json.loads(steps[3]["output_json"])["selection_mode"] == "strict_authoritative"

    listed_runs = WorkflowRepository(database_path).list_for_project(project.id)
    assert listed_runs[0].workflow_name == "guided_autopilot"
    assert [step.step_name for step in listed_runs[0].steps] == [
        "discover_candidates",
        "discover_candidates",
        "select_candidates",
        "select_candidates",
        "ingest_sources",
        "ingest_sources",
        "ingest_sources",
        "ingest_sources",
        "build_knowledge",
        "build_knowledge",
    ]


def test_autopilot_continues_when_one_source_fails_ingestion(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="Dataphin", interaction_mode="guided")
    )
    drafts = [
        _draft("docs", "https://help.aliyun.com/dataphin", "official_docs", 0.95),
        _draft("product", "https://www.alibabacloud.com/product/dataphin", "official_docs", 0.8),
    ]
    build = FakeBuildRunner()

    result = AutopilotWorkflow(
        database_path=database_path,
        discovery_provider=FakeDiscoveryProvider(drafts),
        ingestion_runner=PartiallyFailingIngestionRunner(failing_source_ids={1}),
        build_runner=build,
        search_limit=12,
    ).run(project.id)

    assert result.source_ids == [2]
    assert build.project_ids == [project.id]

    runs = WorkflowRepository(database_path).list_for_project(project.id)
    ingest_step = next(
        step
        for step in reversed(runs[0].steps)
        if step.step_name == "ingest_sources" and step.status in {"completed", "failed"}
    )
    assert ingest_step.output["source_ids"] == [2]
    assert ingest_step.output["failed_sources"][0]["source_id"] == 1
    assert ingest_step.output["failed_sources"][0]["error"] == "URL fetch failed."


def test_autopilot_uses_fallback_sources_when_all_strict_sources_fail(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="旅行代理", interaction_mode="guided")
    )
    drafts = [
        _draft("encyclopedia", "https://encyclopedia.example.com/travel", "encyclopedia", 0.8),
        _draft("official", "https://docs.example.com/travel", "official_docs", 0.75),
        _draft("practical-a", "https://travel.example.com/a", "web", 0.5),
        _draft("practical-b", "https://travel.example.com/b", "web", 0.5),
    ]
    build = FakeBuildRunner()

    result = AutopilotWorkflow(
        database_path=database_path,
        discovery_provider=FakeDiscoveryProvider(drafts),
        ingestion_runner=PartiallyFailingIngestionRunner(failing_source_ids={1, 2}),
        build_runner=build,
        search_limit=12,
    ).run(project.id)

    assert result.selected_count == 4
    assert result.source_ids == [3, 4]
    assert build.project_ids == [project.id]
    runs = WorkflowRepository(database_path).list_for_project(project.id)
    select_step = next(
        step
        for step in reversed(runs[0].steps)
        if step.step_name == "select_candidates" and step.status == "completed"
    )
    assert select_step.output["selection_mode"] == "strict_with_fallback"


def test_autopilot_workflow_uses_fallback_selection_for_practical_domains(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="如何做自媒体", interaction_mode="guided")
    )
    drafts = [
        _draft("creator-a", "https://creator.example.com/a", "web", 0.5),
        _draft("creator-b", "https://creator.example.com/b", "web", 0.5),
        _draft("media", "https://media.example.com/start", "web", 0.5),
    ]
    ingestion = FakeIngestionRunner()
    build = FakeBuildRunner()

    result = AutopilotWorkflow(
        database_path=database_path,
        discovery_provider=FakeDiscoveryProvider(drafts),
        ingestion_runner=ingestion,
        build_runner=build,
        search_limit=12,
    ).run(project.id)

    assert result.selected_count == 3
    assert len(result.source_ids) == 3
    assert build.project_ids == [project.id]

    runs = WorkflowRepository(database_path).list_for_project(project.id)
    select_step = next(
        step
        for step in reversed(runs[0].steps)
        if step.step_name == "select_candidates" and step.status == "completed"
    )
    assert select_step.output["selection_mode"] == "fallback_best_available"


def _draft(
    provider_source_id: str,
    url: str,
    source_type: str,
    authority_score: float,
) -> SourceCandidateDraft:
    return SourceCandidateDraft(
        provider="exa",
        provider_source_id=provider_source_id,
        title=provider_source_id.title(),
        url=url,
        snippet=f"{provider_source_id} snippet",
        source_type=source_type,
        authority_score=authority_score,
        authority_reason="test score",
    )
