from __future__ import annotations

import json

from domain_atlas.core.db import connect, initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateDraft, SourceCandidateRepository
from domain_atlas.domain.sources import SourceRepository
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
    ]


def test_autopilot_workflow_creates_sources_ingests_and_builds(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="LLM Agents", interaction_mode="guided")
    )
    drafts = [
        _draft("official", "https://docs.example.com/agents", "official_docs", 0.91),
        _draft("paper", "https://arxiv.org/abs/2501.12345", "paper", 0.86),
        _draft("blog", "https://blog.example.com/agents", "web", 0.98),
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

    assert discovery.calls == [("LLM Agents", 12)]
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
        "select_candidates",
        "ingest_sources",
        "build_knowledge",
    ]
    assert json.loads(steps[1]["output_json"])["selected_count"] == 2


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
