"""Guided autopilot workflow for one-click domain setup."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.source_candidates import (
    SourceCandidate,
    SourceCandidateDraft,
    SourceCandidateRepository,
)
from domain_atlas.domain.sources import CreateSource, SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository


PREFERRED_SOURCE_TYPES = {
    "official_docs",
    "paper",
    "institution",
    "repository",
    "encyclopedia",
}


class SourceDiscoveryProvider(Protocol):
    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        ...


class IngestionRunner(Protocol):
    def ingest_source(self, source_id: int):
        ...


class BuildRunner(Protocol):
    def run(self, project_id: int):
        ...


@dataclass(frozen=True)
class AutopilotResult:
    selected_count: int
    source_ids: list[int]
    candidate_ids: list[int]


def select_autopilot_candidates(
    candidates: list[SourceCandidateDraft],
    *,
    max_sources: int = 5,
    min_authority_score: float = 0.65,
    max_per_domain: int = 2,
) -> list[SourceCandidateDraft]:
    """Select high-authority candidates for guided mode."""
    eligible = [
        candidate
        for candidate in candidates
        if candidate.authority_score >= min_authority_score
        and candidate.source_type in PREFERRED_SOURCE_TYPES
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (
            item.source_type not in PREFERRED_SOURCE_TYPES,
            -item.authority_score,
            item.title,
        ),
    )
    selected: list[SourceCandidateDraft] = []
    domain_counts: dict[str, int] = defaultdict(int)
    for candidate in ranked:
        domain = _domain(candidate.url)
        if domain_counts[domain] >= max_per_domain:
            continue
        selected.append(candidate)
        domain_counts[domain] += 1
        if len(selected) >= max_sources:
            break
    return selected


class AutopilotWorkflow:
    """Run guided mode: search, filter, accept, ingest, and build."""

    def __init__(
        self,
        *,
        database_path: Path,
        discovery_provider: SourceDiscoveryProvider,
        ingestion_runner: IngestionRunner,
        build_runner: BuildRunner,
        search_limit: int = 12,
    ) -> None:
        self.project_repository = DomainProjectRepository(database_path)
        self.candidate_repository = SourceCandidateRepository(database_path)
        self.source_repository = SourceRepository(database_path)
        self.workflow_repository = WorkflowRepository(database_path)
        self.discovery_provider = discovery_provider
        self.ingestion_runner = ingestion_runner
        self.build_runner = build_runner
        self.search_limit = search_limit

    def run(self, project_id: int) -> AutopilotResult:
        project = self.project_repository.get(project_id)
        if project is None:
            raise ValueError("Domain project not found.")

        run_id = self.workflow_repository.start_run(project_id, "guided_autopilot")
        try:
            drafts = self.discovery_provider.search(project.name, limit=self.search_limit)
            persisted = self.candidate_repository.replace_discovered(project_id, drafts)
            self.workflow_repository.record_step(
                run_id,
                step_name="discover_candidates",
                status="completed",
                output={"candidate_count": len(persisted)},
            )

            selected_drafts = select_autopilot_candidates(drafts)
            if not selected_drafts:
                raise ValueError("No authoritative candidates passed guided mode filtering.")
            selected_source_ids = {candidate.provider_source_id for candidate in selected_drafts}
            selected = [
                candidate
                for candidate in persisted
                if candidate.provider_source_id in selected_source_ids
            ]
            self.workflow_repository.record_step(
                run_id,
                step_name="select_candidates",
                status="completed",
                output={
                    "selected_count": len(selected),
                    "candidate_ids": [candidate.id for candidate in selected],
                },
            )

            source_ids: list[int] = []
            failed_sources: list[dict[str, object]] = []
            for candidate in selected:
                accepted = self.candidate_repository.accept(project_id, candidate.id)
                if accepted is None:
                    continue
                source = self._source_from_candidate(project_id, accepted)
                try:
                    self.ingestion_runner.ingest_source(source.id)
                except Exception as exc:
                    failed_sources.append(
                        {
                            "source_id": source.id,
                            "candidate_id": candidate.id,
                            "title": candidate.title,
                            "url": candidate.url,
                            "error": str(exc),
                        }
                    )
                    continue
                source_ids.append(source.id)

            self.workflow_repository.record_step(
                run_id,
                step_name="ingest_sources",
                status="completed" if source_ids else "failed",
                output={"source_ids": source_ids, "failed_sources": failed_sources},
            )
            if not source_ids:
                raise ValueError("All selected sources failed ingestion.")
            self.build_runner.run(project_id)
            self.workflow_repository.record_step(
                run_id,
                step_name="build_knowledge",
                status="completed",
                output={"status": "completed"},
            )
            self.workflow_repository.finish_run(run_id)
            return AutopilotResult(
                selected_count=len(selected),
                source_ids=source_ids,
                candidate_ids=[candidate.id for candidate in selected],
            )
        except Exception as exc:
            self.workflow_repository.record_step(
                run_id,
                step_name="guided_autopilot",
                status="failed",
                error=str(exc),
            )
            self.workflow_repository.fail_run(run_id, str(exc))
            raise

    def _source_from_candidate(self, project_id: int, candidate: SourceCandidate):
        return self.source_repository.create(
            CreateSource(
                project_id=project_id,
                source_type="url",
                title=candidate.title,
                locator=candidate.url,
                metadata={
                    "candidate_id": candidate.id,
                    "provider": candidate.provider,
                    "authority_score": candidate.authority_score,
                    "authority_reason": candidate.authority_reason,
                    "auto_accepted": True,
                },
            )
        )


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host
