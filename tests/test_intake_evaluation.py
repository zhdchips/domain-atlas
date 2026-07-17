from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain_atlas.intake.assessment import IntakeAssessment, fallback_intake_assessment
from domain_atlas.intake.evaluation import (
    IntakeEvaluationError,
    RecordedIntakeAssessmentProvider,
    evaluate_case,
    evaluate_case_set,
    load_case_set,
    render_report,
    write_report,
)


CASE_SET_PATH = Path(__file__).resolve().parents[1] / "evals" / "intake" / "cases.v1.json"


def test_recorded_offline_case_set_passes_all_quality_checks(tmp_path):
    case_set = load_case_set(CASE_SET_PATH)
    report = evaluate_case_set(
        case_set,
        RecordedIntakeAssessmentProvider(case_set.cases),
        mode="offline",
        generated_at=datetime.now(UTC).isoformat(),
    )
    path = tmp_path / "offline-report.json"
    write_report(report, path)

    assert len(case_set.cases) >= 12
    assert {"Agent", "数据治理", "产品运营", "瓴羊 Dataphin"} <= {case.name for case in case_set.cases}
    assert report.gate_passed is True
    assert report.metrics["decision_accuracy"] == 1.0
    assert report.metrics["clarification_structure_rate"] == 1.0
    assert report.metrics["topic_coverage_rate"] == 1.0
    assert "offline_payload" not in path.read_text(encoding="utf-8")
    assert "quality_gate failures=none" in render_report(report)


def test_evaluator_detects_false_pass_and_core_gate_failure():
    case_set = load_case_set(CASE_SET_PATH)
    report = evaluate_case_set(
        case_set,
        DirectCreateProvider(),
        mode="offline",
        generated_at="2026-07-17T00:00:00+00:00",
    )

    agent = next(result for result in report.results if result.case_id == "agent-ambiguous")
    assert agent.actual_decision == "clear"
    assert "decision_mismatch" in agent.failure_categories
    assert report.metrics["false_pass_rate"] > 0
    assert report.gate_passed is False
    assert "core:agent-ambiguous" in report.gate_failures


def test_evaluator_reports_safe_fallback_without_provider_error_text():
    case_set = load_case_set(CASE_SET_PATH)
    agent = next(case for case in case_set.cases if case.id == "agent-ambiguous")

    result = evaluate_case(agent, FailingProvider())

    assert result.status == "fallback"
    assert result.checks["assessment_available"] is False
    assert result.checks["fallback_safe"] is True
    assert "provider_error" in result.failure_categories
    assert result.passed is False
    assert "network secret should not escape" not in render_report(
        evaluate_case_set(
            case_set,
            FailingProvider(),
            mode="offline",
            generated_at="2026-07-17T00:00:00+00:00",
        )
    )


def test_evaluator_rejects_missing_topics_and_invalid_candidate_structure():
    case_set = load_case_set(CASE_SET_PATH)
    agent = next(case for case in case_set.cases if case.id == "agent-ambiguous")

    result = evaluate_case(agent, BrokenClarificationProvider())

    assert result.actual_decision == "clarify"
    assert result.checks["structure_valid"] is False
    assert result.checks["topic_coverage"] is False
    assert {"invalid_structure", "missing_required_topics"} <= set(result.failure_categories)


def test_evaluator_flags_sensitive_content_from_an_untrusted_provider():
    case_set = load_case_set(CASE_SET_PATH)
    clear_case = next(case for case in case_set.cases if case.id == "dataphin-specific-clear")

    result = evaluate_case(clear_case, SensitiveProvider())

    assert result.checks["sensitive_content_safe"] is False
    assert "sensitive_content" in result.failure_categories
    assert result.passed is False


def test_case_loader_rejects_invalid_schema(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version": 1, "case_set": "broken", "quality_gate": {}, "cases": []}', encoding="utf-8")

    with pytest.raises(IntakeEvaluationError):
        load_case_set(path)


class DirectCreateProvider:
    def assess(self, *, name: str, goal: str, level: str):
        return fallback_intake_assessment(name=name, goal=goal, level=level)


class FailingProvider:
    def assess(self, **kwargs):
        raise RuntimeError("network secret should not escape")


class BrokenClarificationProvider:
    def assess(self, *, name: str, goal: str, level: str):
        return IntakeAssessment(
            needs_clarification=True,
            reason="需要澄清。",
            understanding=f"{name} 范围较宽。",
            question="从哪开始？",
            options=[
                {"value": "same", "label": "同一方向", "description": "没有要求的主题。", "scope": "同一范围"},
                {"value": "same", "label": "重复方向", "description": "没有要求的主题。", "scope": "同一范围"},
            ],
            default_scope="同一范围",
            assumptions=[],
            confidence=0.8,
            recommended_option="same",
        )


class SensitiveProvider:
    def assess(self, *, name: str, goal: str, level: str):
        return IntakeAssessment(
            needs_clarification=False,
            reason="api key should never be in an assessment",
            understanding=f"将围绕{name}学习。",
            question="",
            options=[],
            default_scope=name,
            assumptions=[],
            confidence=0.9,
        )
