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
MIN_BUILD_SOURCES = 2
MAX_SOURCES_PER_DOMAIN = 2


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


@dataclass(frozen=True)
class SourceAttempt:
    candidate_id: int
    source_id: int
    title: str
    url: str
    outcome: str
    error_category: str = ""
    detail: str = ""
    retryable: bool = False

    def to_output(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "outcome": self.outcome,
            "error_category": self.error_category,
            "detail": self.detail,
            "retryable": self.retryable,
        }


def select_autopilot_candidates(
    candidates: list[SourceCandidateDraft],
    *,
    max_sources: int = 5,
    min_authority_score: float = 0.65,
    fallback_min_authority_score: float = 0.5,
    max_per_domain: int = 2,
) -> list[SourceCandidateDraft]:
    """Return the first display-sized slice of the guided candidate queue."""
    return build_autopilot_candidate_queue(
        candidates,
        min_authority_score=min_authority_score,
        fallback_min_authority_score=fallback_min_authority_score,
        max_per_domain=max_per_domain,
    )[:max_sources]


def build_autopilot_candidate_queue(
    candidates: list[SourceCandidateDraft],
    *,
    min_authority_score: float = 0.65,
    fallback_min_authority_score: float = 0.5,
    max_per_domain: int = MAX_SOURCES_PER_DOMAIN,
) -> list[SourceCandidateDraft]:
    """Rank every usable candidate so ingestion can replenish after failures."""
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
        max_sources=None,
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
    seen_provider_ids: set[str] = set()
    seen_urls: set[str] = set()
    unique: list[SourceCandidateDraft] = []
    for candidate in candidates:
        normalized_url = candidate.url.rstrip("/")
        if candidate.provider_source_id in seen_provider_ids or normalized_url in seen_urls:
            continue
        seen_provider_ids.add(candidate.provider_source_id)
        seen_urls.add(normalized_url)
        unique.append(candidate)
    return unique


def _select_ranked_candidates(
    candidates: list[SourceCandidateDraft],
    *,
    max_sources: int | None,
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
        if max_sources is not None and len(selected) >= max_sources:
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
        self.minimum_build_sources = MIN_BUILD_SOURCES

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
            candidate_queue = build_autopilot_candidate_queue(drafts)
            if not candidate_queue:
                raise ValueError("No usable candidates passed guided mode filtering.")
            persisted_by_provider_id = {
                candidate.provider_source_id: candidate for candidate in persisted
            }
            selected = [
                persisted_by_provider_id[candidate.provider_source_id]
                for candidate in candidate_queue
                if candidate.provider_source_id in persisted_by_provider_id
            ]
            self.workflow_repository.record_step(
                run_id,
                step_name="select_candidates",
                status="completed",
                output={
                    "selected_count": len(selected),
                    "queued_count": len(selected),
                    "minimum_build_sources": self.minimum_build_sources,
                    "candidate_ids": [candidate.id for candidate in selected],
                    "selection_mode": _selection_mode(candidate_queue),
                },
            )

            source_ids: list[int] = []
            failed_sources: list[dict[str, object]] = []
            attempts: list[SourceAttempt] = []
            self.workflow_repository.record_step(
                run_id,
                step_name="ingest_sources",
                status="running",
                output={
                    "completed": 0,
                    "total": len(selected),
                    "minimum_build_sources": self.minimum_build_sources,
                },
            )
            for candidate in selected:
                accepted = self.candidate_repository.accept(project_id, candidate.id)
                if accepted is None:
                    continue
                source = self._source_from_candidate(project_id, accepted)
                try:
                    self.ingestion_runner.ingest_source(source.id)
                except Exception as exc:
                    category, retryable = classify_ingestion_failure(exc)
                    attempt = SourceAttempt(
                        candidate_id=candidate.id,
                        source_id=source.id,
                        title=candidate.title,
                        url=candidate.url,
                        outcome="failed",
                        error_category=category,
                        detail=str(exc),
                        retryable=retryable,
                    )
                    attempts.append(attempt)
                    failed_sources.append(
                        {
                            "source_id": source.id,
                            "candidate_id": candidate.id,
                            "title": candidate.title,
                            "url": candidate.url,
                            "error": str(exc),
                            "error_category": category,
                            "retryable": retryable,
                        }
                    )
                    self.workflow_repository.record_step(
                        run_id,
                        step_name="ingest_sources",
                        status="running",
                        output=_ingestion_progress_output(
                            source_ids=source_ids,
                            attempts=attempts,
                            queue_size=len(selected),
                            minimum_build_sources=self.minimum_build_sources,
                        ),
                    )
                    continue
                source_ids.append(source.id)
                attempts.append(
                    SourceAttempt(
                        candidate_id=candidate.id,
                        source_id=source.id,
                        title=candidate.title,
                        url=candidate.url,
                        outcome="ingested",
                    )
                )
                self.workflow_repository.record_step(
                    run_id,
                    step_name="ingest_sources",
                    status="running",
                    output=_ingestion_progress_output(
                        source_ids=source_ids,
                        attempts=attempts,
                        queue_size=len(selected),
                        minimum_build_sources=self.minimum_build_sources,
                        source_id=source.id,
                    ),
                )

                if len(source_ids) >= self.minimum_build_sources:
                    break

            terminal_reason = (
                "minimum_sources_reached"
                if len(source_ids) >= self.minimum_build_sources
                else "candidates_exhausted"
            )
            self.workflow_repository.record_step(
                run_id,
                step_name="ingest_sources",
                status="completed" if terminal_reason == "minimum_sources_reached" else "failed",
                output={
                    **_ingestion_progress_output(
                        source_ids=source_ids,
                        attempts=attempts,
                        queue_size=len(selected),
                        minimum_build_sources=self.minimum_build_sources,
                    ),
                    "source_ids": source_ids,
                    "failed_sources": failed_sources,
                    "terminal_reason": terminal_reason,
                    "recovery_message": _recovery_message(
                        successful_sources=len(source_ids),
                        minimum_build_sources=self.minimum_build_sources,
                        attempts=attempts,
                    ),
                },
            )
            if terminal_reason == "candidates_exhausted":
                raise ValueError(
                    _recovery_message(
                        successful_sources=len(source_ids),
                        minimum_build_sources=self.minimum_build_sources,
                        attempts=attempts,
                    )
                )
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


def classify_ingestion_failure(error: Exception) -> tuple[str, bool]:
    """Return a stable learner-recovery category without leaking provider internals."""
    messages = _error_messages(error)
    text = " ".join(messages).lower()
    if "http 401" in text or "http 403" in text or "access denied" in text:
        return "access_denied", False
    if "timeout" in text or "timed out" in text:
        return "timeout", True
    if "embedding" in text or "vector" in text:
        return "embedding", True
    if any(
        marker in text
        for marker in (
            "extractable text",
            "produce any chunks",
            "unsupported source",
            "pdf",
            "parse",
        )
    ):
        return "parse", False
    if "url fetch failed" in text or "connect" in text or "network" in text:
        return "network", True
    return "unknown", True


def _error_messages(error: Exception) -> list[str]:
    messages: list[str] = []
    current: BaseException | None = error
    while current is not None:
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    return messages


def _ingestion_progress_output(
    *,
    source_ids: list[int],
    attempts: list[SourceAttempt],
    queue_size: int,
    minimum_build_sources: int,
    source_id: int | None = None,
) -> dict[str, object]:
    output: dict[str, object] = {
        "completed": len(source_ids),
        "total": queue_size,
        "success_count": len(source_ids),
        "attempted_count": len(attempts),
        "failed_count": sum(attempt.outcome == "failed" for attempt in attempts),
        "minimum_build_sources": minimum_build_sources,
        "attempted_sources": [attempt.to_output() for attempt in attempts],
    }
    if source_id is not None:
        output["source_id"] = source_id
    return output


def _recovery_message(
    *,
    successful_sources: int,
    minimum_build_sources: int,
    attempts: list[SourceAttempt],
) -> str:
    if successful_sources >= minimum_build_sources:
        return f"已获得 {successful_sources} 份可用资料，开始构建知识库。"
    failed_categories = sorted(
        {attempt.error_category for attempt in attempts if attempt.error_category}
    )
    category_text = "、".join(_failure_category_label(category) for category in failed_categories)
    detail = f"失败原因包括：{category_text}。" if category_text else ""
    return (
        f"候选资料已尝试完毕，仅成功摄取 {successful_sources}/{minimum_build_sources} 份。"
        f"{detail}可稍后重试，或手动添加可访问的 URL、Markdown/PDF，也可调整领域范围后重新搜索。"
    )


def _failure_category_label(category: str) -> str:
    return {
        "access_denied": "访问受限",
        "network": "网络请求失败",
        "timeout": "请求超时",
        "parse": "内容解析失败",
        "embedding": "向量化失败",
        "unknown": "未知错误",
    }.get(category, category)
