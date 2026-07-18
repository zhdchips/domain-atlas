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
    fallback_min_authority_score: float = 0.5,
    max_per_domain: int = 2,
) -> list[SourceCandidateDraft]:
    """Select high-authority candidates for guided mode."""
    strict_eligible = [
        candidate
        for candidate in candidates
        if candidate.authority_score >= min_authority_score
        and candidate.source_type in PREFERRED_SOURCE_TYPES
    ]
    fallback_eligible = [
        candidate
        for candidate in candidates
        if candidate.authority_score >= fallback_min_authority_score
    ]
    # A small fallback set keeps guided mode productive when the top authoritative
    # pages are blocked by anti-bot controls or are otherwise not ingestible.
    eligible = _unique_candidates([*strict_eligible, *fallback_eligible])
    return _select_ranked_candidates(
        eligible,
        max_sources=max_sources,
        max_per_domain=max_per_domain,
    )


def _selection_mode(selected: list[SourceCandidateDraft]) -> str:
    if all(
        candidate.authority_score >= 0.65 and candidate.source_type in PREFERRED_SOURCE_TYPES
        for candidate in selected
    ):
        return "strict_authoritative"
    if any(
        candidate.authority_score >= 0.65 and candidate.source_type in PREFERRED_SOURCE_TYPES
        for candidate in selected
    ):
        return "strict_with_fallback"
    return "fallback_best_available"


def _unique_candidates(candidates: list[SourceCandidateDraft]) -> list[SourceCandidateDraft]:
    seen: set[str] = set()
    unique: list[SourceCandidateDraft] = []
    for candidate in candidates:
        if candidate.provider_source_id in seen:
            continue
        seen.add(candidate.provider_source_id)
        unique.append(candidate)
    return unique


def _select_ranked_candidates(
    candidates: list[SourceCandidateDraft],
    *,
    max_sources: int,
    max_per_domain: int,
) -> list[SourceCandidateDraft]:
    ranked = sorted(
        candidates,
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

    def run(self, project_id: int, *, run_id: int | None = None) -> AutopilotResult:
        if run_id is None:
            run_id = self.workflow_repository.start_run(project_id, "guided_autopilot")
        else:
            self.workflow_repository.mark_running(run_id)
        try:
            project = self.project_repository.get(project_id)
            if project is None:
                raise ValueError("Domain project not found.")
            self.workflow_repository.record_step(
                run_id, step_name="discover_candidates", status="running"
            )
            drafts = self.discovery_provider.search(project.effective_scope, limit=self.search_limit)
            persisted = self.candidate_repository.replace_discovered(project_id, drafts)
            self.workflow_repository.record_step(
                run_id,
                step_name="discover_candidates",
                status="completed",
                output={"candidate_count": len(persisted)},
            )

            self.workflow_repository.record_step(
                run_id, step_name="select_candidates", status="running"
            )
            selected_drafts = select_autopilot_candidates(drafts)
            if not selected_drafts:
                raise ValueError("No usable candidates passed guided mode filtering.")
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
                    "selection_mode": _selection_mode(selected_drafts),
                },
            )

            source_ids: list[int] = []
            failed_sources: list[dict[str, object]] = []
            self.workflow_repository.record_step(
                run_id,
                step_name="ingest_sources",
                status="running",
                output={"completed": 0, "total": len(selected)},
            )
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
                    status="running",
                    output={"completed": len(source_ids), "total": len(selected), "source_id": source.id},
                )

            self.workflow_repository.record_step(
                run_id,
                step_name="ingest_sources",
                status="completed" if source_ids else "failed",
                output={"source_ids": source_ids, "failed_sources": failed_sources},
            )
            if not source_ids:
                raise ValueError("All selected sources failed ingestion.")
            self.workflow_repository.record_step(
                run_id,
                step_name="build_knowledge",
                status="running",
            )
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
