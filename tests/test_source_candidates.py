from __future__ import annotations

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import (
    SourceCandidateDraft,
    SourceCandidateRepository,
)


def test_candidate_repository_replaces_discovered_and_accepts(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    repository = SourceCandidateRepository(database_path)

    candidates = repository.replace_discovered(
        project.id,
        [
            SourceCandidateDraft(
                provider="exa",
                provider_source_id="src-1",
                title="Agent Docs",
                url="https://docs.example.com/agents",
                snippet="Docs",
                source_type="official_docs",
                authority_score=0.9,
                authority_reason="官方资料",
            ),
            SourceCandidateDraft(
                provider="exa",
                provider_source_id="src-2",
                title="Agent Blog",
                url="https://example.com/blog",
                snippet="Blog",
                authority_score=0.5,
                authority_reason="通用网页资料",
            ),
        ],
    )

    assert [candidate.title for candidate in candidates] == ["Agent Docs", "Agent Blog"]
    accepted = repository.accept(project.id, candidates[0].id)

    assert accepted is not None
    assert accepted.status == "accepted"
    listed = repository.list_for_project(project.id)
    assert listed[0].status == "accepted"

    repository.replace_discovered(
        project.id,
        [
            SourceCandidateDraft(
                provider="exa",
                provider_source_id="src-3",
                title="New Candidate",
                url="https://new.example.com",
                snippet="New",
            )
        ],
    )

    titles = [candidate.title for candidate in repository.list_for_project(project.id)]
    assert titles == ["Agent Docs", "New Candidate"]
