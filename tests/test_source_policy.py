from __future__ import annotations

from domain_atlas.domain.source_candidates import SourceCandidateDraft
from domain_atlas.workflow.source_policy import build_selection_plan


def test_service_workflow_requires_direct_authority_and_collapses_github_fork():
    original = _draft(
        "origin",
        "https://github.com/Ryujoxys/sushiro-overdose",
        "repository",
        0.51,
    )
    fork = _draft(
        "fork",
        "https://github.com/YANG-CHUNXU/sushiro-overdose",
        "repository",
        0.51,
    )
    news = _draft("news", "https://news.example.com/sushiro", "web", 0.5)

    plan = build_selection_plan("寿司郎在线取号流程", [original, fork, news])

    assert plan.requires_direct_authority is True
    assert plan.queue == []
    assert "未找到" in plan.evidence_insufficient_reason
    roles = {candidate.provider_source_id: candidate.metadata["source_role"] for candidate in plan.assessed}
    assert roles == {"origin": "repository", "fork": "mirror_or_fork", "news": "independent_coverage"}
    assert plan.assessed[1].metadata["duplicate_of"] == "origin"


def test_open_source_scope_allows_repository_and_distinct_document_families():
    repository = _draft(
        "repo",
        "https://github.com/example/agent-sdk",
        "repository",
        0.51,
    )
    documentation = _draft(
        "docs",
        "https://docs.example.com/agent-sdk",
        "official_docs",
        0.75,
    )

    plan = build_selection_plan("某开源 Agent SDK 的使用与实现", [repository, documentation])

    assert plan.requires_direct_authority is False
    assert [candidate.provider_source_id for candidate in plan.queue] == ["docs", "repo"]
    assert len({candidate.metadata["source_family"] for candidate in plan.queue}) == 2


def test_direct_document_and_institution_are_independent_guided_evidence():
    document = _draft("official", "https://help.example.com/rules", "official_docs", 0.75)
    institution = _draft("institution", "https://gov.example.org/rules", "institution", 0.72)

    plan = build_selection_plan("某平台服务办理流程", [document, institution])

    assert plan.requires_direct_authority is True
    assert [candidate.provider_source_id for candidate in plan.queue] == ["official", "institution"]


def _draft(
    provider_source_id: str,
    url: str,
    source_type: str,
    authority_score: float,
) -> SourceCandidateDraft:
    return SourceCandidateDraft(
        provider="fixture",
        provider_source_id=provider_source_id,
        title=provider_source_id,
        url=url,
        snippet=f"{provider_source_id} source",
        source_type=source_type,
        authority_score=authority_score,
        authority_reason="fixture",
    )
