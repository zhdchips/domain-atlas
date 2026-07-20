from __future__ import annotations

from domain_atlas.domain.source_candidates import SourceCandidateDraft
from domain_atlas.workflow.candidate_assessment import (
    LLMCandidateAssessmentProvider,
    apply_candidate_assessment,
    rank_assessed_candidates,
    rank_candidates_deterministically,
    resolve_candidate_assessment,
    validate_candidate_assessment_payload,
)


def test_candidate_assessment_validates_complete_bounded_batch():
    candidates = [_draft("creator"), _draft("report")]
    result = validate_candidate_assessment_payload(_payload(), candidates=candidates)

    assert result is not None
    assert result.confidence == 0.88
    assert result.assessments["report"].priority == 1
    assert result.supplemental_queries == ["短视频创作者官方规则"]


def test_candidate_assessment_rejects_unknown_or_missing_candidate_ids():
    candidates = [_draft("creator"), _draft("report")]
    payload = _payload()
    payload["candidate_assessments"][1]["candidate_id"] = "unknown"

    assert validate_candidate_assessment_payload(payload, candidates=candidates) is None


def test_candidate_assessment_rejects_unsafe_supplemental_query():
    candidates = [_draft("creator"), _draft("report")]
    payload = _payload()
    payload["supplemental_queries"] = ["https://example.com official docs"]

    assert validate_candidate_assessment_payload(payload, candidates=candidates) is None


def test_candidate_assessment_provider_uses_strict_json_contract():
    class FakeChat:
        def complete_json(self, *, system_prompt: str, user_prompt: str):
            assert "untrusted data" in system_prompt
            assert "creator" in user_prompt
            return _payload()

    result = LLMCandidateAssessmentProvider(FakeChat()).assess(
        scope="短视频自媒体入门与运营",
        goal="学习内容生产与运营",
        language="zh",
        candidates=[_draft("creator"), _draft("report")],
    )

    assert result is not None
    assert result.assessments["creator"].risk_flags == ["marketing_heavy"]


def test_rank_assessed_candidates_skips_off_topic_and_preserves_direct_evidence():
    candidates = [_draft("creator"), _draft("report"), _draft("official", direct=True)]
    payload = _payload()
    payload["candidate_assessments"].append(
        {
            "candidate_id": "official",
            "relevance": 0.6,
            "authority": 0.6,
            "coverage_topics": ["服务规则"],
            "risk_flags": [],
            "priority": 4,
            "selection_reason": "提供可验证的一方规则。",
        }
    )
    result = validate_candidate_assessment_payload(payload, candidates=candidates)

    assert result is not None
    ranked = rank_assessed_candidates(candidates, result, requires_direct_authority=True)

    assert [candidate.provider_source_id for candidate in ranked] == ["official", "report", "creator"]


def test_rank_assessed_candidates_excludes_blocking_risk():
    candidates = [_draft("creator"), _draft("report")]
    payload = _payload()
    payload["candidate_assessments"][0]["risk_flags"] = ["low_quality"]
    result = validate_candidate_assessment_payload(payload, candidates=candidates)

    assert result is not None
    assert [candidate.provider_source_id for candidate in rank_assessed_candidates(candidates, result, requires_direct_authority=False)] == ["report"]


def test_deterministic_fallback_keeps_low_score_broad_domain_candidates():
    candidates = [_draft("creator", score=0.43), _draft("report", score=0.43)]

    ranked = rank_candidates_deterministically(candidates, requires_direct_authority=False)

    assert [candidate.provider_source_id for candidate in ranked] == ["creator", "report"]


def test_candidate_assessment_resolver_reports_invalid_and_low_confidence_without_throwing():
    class InvalidProvider:
        def assess(self, **kwargs):
            return None

    class LowConfidenceProvider:
        def assess(self, **kwargs):
            return validate_candidate_assessment_payload(_payload(), candidates=kwargs["candidates"])

    candidates = [_draft("creator"), _draft("report")]
    assert resolve_candidate_assessment(
        provider=InvalidProvider(),
        scope="短视频自媒体",
        goal="",
        language="zh",
        candidates=candidates,
        min_confidence=0.6,
    )[2] == "invalid"
    assert resolve_candidate_assessment(
        provider=LowConfidenceProvider(),
        scope="短视频自媒体",
        goal="",
        language="zh",
        candidates=candidates,
        min_confidence=0.9,
    )[2] == "low_confidence"


def _draft(candidate_id: str, *, score: float = 0.43, direct: bool = False) -> SourceCandidateDraft:
    return SourceCandidateDraft(
        provider="fixture",
        provider_source_id=candidate_id,
        title=candidate_id,
        url=f"https://{candidate_id}.example.com/article",
        snippet=f"{candidate_id} source",
        source_type="web",
        authority_score=score,
        metadata={"source_role": "first_party" if direct else "independent_coverage", "is_direct_authority": direct},
    )


def _payload() -> dict:
    return {
        "confidence": 0.88,
        "candidate_assessments": [
            {
                "candidate_id": "creator",
                "relevance": 0.76,
                "authority": 0.42,
                "coverage_topics": ["账号定位"],
                "risk_flags": ["marketing_heavy"],
                "priority": 2,
                "selection_reason": "提供入门实践背景，但营销内容较多。",
            },
            {
                "candidate_id": "report",
                "relevance": 0.82,
                "authority": 0.81,
                "coverage_topics": ["内容生产", "运营指标"],
                "risk_flags": [],
                "priority": 1,
                "selection_reason": "覆盖核心方法并具备较高可追溯性。",
            },
        ],
        "missing_coverage": ["平台规则"],
        "supplemental_queries": ["短视频创作者官方规则"],
    }
