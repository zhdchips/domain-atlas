"""Versioned, non-sensitive evaluation for project intake assessments."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from domain_atlas.intake.assessment import (
    IntakeAssessment,
    IntakeAssessmentProvider,
    fallback_intake_assessment,
    validate_assessment_payload,
)


class IntakeEvaluationError(ValueError):
    """Raised when a versioned evaluation case set is malformed."""


@dataclass(frozen=True)
class IntakeEvalCase:
    id: str
    core: bool
    category: str
    name: str
    goal: str
    level: str
    expected_decision: str
    required_topics: tuple[str, ...]
    notes: str
    offline_payload: dict[str, Any]


@dataclass(frozen=True)
class IntakeEvalCaseSet:
    schema_version: int
    name: str
    quality_gate: dict[str, float]
    cases: tuple[IntakeEvalCase, ...]


@dataclass(frozen=True)
class IntakeEvalResult:
    case_id: str
    category: str
    core: bool
    expected_decision: str
    actual_decision: str
    status: str
    confidence: float | None
    passed: bool
    failure_categories: tuple[str, ...]
    checks: dict[str, bool]
    elapsed_ms: int


@dataclass(frozen=True)
class IntakeEvalReport:
    report_version: int
    case_set: str
    schema_version: int
    mode: str
    generated_at: str
    results: tuple[IntakeEvalResult, ...]
    metrics: dict[str, float | int]
    gate_passed: bool
    gate_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": self.report_version,
            "case_set": self.case_set,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "results": [asdict(result) for result in self.results],
            "metrics": self.metrics,
            "gate_passed": self.gate_passed,
            "gate_failures": list(self.gate_failures),
        }


class RecordedIntakeAssessmentProvider:
    """Replay recorded, validated case payloads without calling a provider."""

    def __init__(self, cases: tuple[IntakeEvalCase, ...]) -> None:
        self._payloads = {(case.name, case.goal, case.level): case.offline_payload for case in cases}

    def assess(self, *, name: str, goal: str, level: str) -> IntakeAssessment | None:
        payload = self._payloads.get((name, goal, level))
        return validate_assessment_payload(payload, domain_name=name)


def load_case_set(path: Path) -> IntakeEvalCaseSet:
    """Load a small, strict JSON case set that can be reviewed in version control."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeEvaluationError(f"Cannot load intake evaluation case set: {path.name}") from exc
    if not isinstance(payload, dict):
        raise IntakeEvaluationError("Intake evaluation case set must be a JSON object.")
    schema_version = payload.get("schema_version")
    case_set = payload.get("case_set")
    gate = payload.get("quality_gate")
    raw_cases = payload.get("cases")
    if not isinstance(schema_version, int) or schema_version < 1 or not isinstance(case_set, str):
        raise IntakeEvaluationError("Case set requires schema_version and case_set.")
    if not isinstance(gate, dict) or not isinstance(raw_cases, list) or not raw_cases:
        raise IntakeEvaluationError("Case set requires quality_gate and non-empty cases.")
    quality_gate = _parse_quality_gate(gate)
    cases = tuple(_parse_case(item) for item in raw_cases)
    if len({case.id for case in cases}) != len(cases):
        raise IntakeEvaluationError("Case ids must be unique.")
    if not any(case.core for case in cases):
        raise IntakeEvaluationError("Case set requires at least one core case.")
    return IntakeEvalCaseSet(schema_version, case_set.strip(), quality_gate, cases)


def evaluate_case(case: IntakeEvalCase, provider: IntakeAssessmentProvider) -> IntakeEvalResult:
    """Evaluate one assessment without retaining raw responses or provider errors."""
    started = time.monotonic()
    failure_categories: list[str] = []
    status = "assessed"
    try:
        assessment = provider.assess(name=case.name, goal=case.goal, level=case.level)
    except Exception:
        assessment = fallback_intake_assessment(name=case.name, goal=case.goal, level=case.level)
        status = "fallback"
        failure_categories.append("provider_error")
    if assessment is None:
        assessment = fallback_intake_assessment(name=case.name, goal=case.goal, level=case.level)
        status = "fallback"
        failure_categories.append("invalid_assessment")

    checks = _assessment_checks(case, assessment, status=status)
    if not checks["assessment_available"]:
        failure_categories.append("fallback_used")
    if not checks["decision_match"]:
        failure_categories.append("decision_mismatch")
    if not checks["structure_valid"]:
        failure_categories.append("invalid_structure")
    if not checks["topic_coverage"]:
        failure_categories.append("missing_required_topics")
    if not checks["sensitive_content_safe"]:
        failure_categories.append("sensitive_content")
    if not checks["fallback_safe"]:
        failure_categories.append("unsafe_fallback")
    passed = all(checks.values())
    return IntakeEvalResult(
        case_id=case.id,
        category=case.category,
        core=case.core,
        expected_decision=case.expected_decision,
        actual_decision=assessment.decision,
        status=status,
        confidence=assessment.confidence,
        passed=passed,
        failure_categories=tuple(failure_categories),
        checks=checks,
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )


def evaluate_case_set(
    case_set: IntakeEvalCaseSet,
    provider: IntakeAssessmentProvider,
    *,
    mode: str,
    generated_at: str,
) -> IntakeEvalReport:
    if mode not in {"offline", "live"}:
        raise IntakeEvaluationError("Evaluation mode must be offline or live.")
    results = tuple(evaluate_case(case, provider) for case in case_set.cases)
    metrics = _metrics(results)
    gate_passed, gate_failures = _quality_gate(case_set, results, metrics)
    return IntakeEvalReport(
        report_version=1,
        case_set=case_set.name,
        schema_version=case_set.schema_version,
        mode=mode,
        generated_at=generated_at,
        results=results,
        metrics=metrics,
        gate_passed=gate_passed,
        gate_failures=tuple(gate_failures),
    )


def write_report(report: IntakeEvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(report: IntakeEvalReport) -> str:
    metrics = report.metrics
    lines = [
        f"Intake evaluation mode={report.mode} case_set={report.case_set}",
        (
            "metrics "
            f"decision_accuracy={metrics['decision_accuracy']:.2%} "
            f"false_interrupt_rate={metrics['false_interrupt_rate']:.2%} "
            f"false_pass_rate={metrics['false_pass_rate']:.2%} "
            f"structure_rate={metrics['clarification_structure_rate']:.2%} "
            f"topic_coverage_rate={metrics['topic_coverage_rate']:.2%}"
        ),
    ]
    for result in report.results:
        outcome = "PASS" if result.passed else "FAIL"
        details = ",".join(result.failure_categories) or "ok"
        lines.append(
            f"{outcome} {result.case_id} expected={result.expected_decision} "
            f"actual={result.actual_decision} status={result.status} details={details}"
        )
    gate = "PASS" if report.gate_passed else "FAIL"
    lines.append(f"{gate} quality_gate failures={','.join(report.gate_failures) or 'none'}")
    return "\n".join(lines)


def _parse_quality_gate(value: dict[str, Any]) -> dict[str, float]:
    keys = {
        "min_decision_accuracy",
        "min_topic_coverage_rate",
        "require_clarification_structure_rate",
    }
    if set(value) != keys:
        raise IntakeEvaluationError("quality_gate keys are invalid.")
    parsed: dict[str, float] = {}
    for key in keys:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not 0 <= float(raw) <= 1:
            raise IntakeEvaluationError(f"quality_gate {key} must be a number from 0 to 1.")
        parsed[key] = float(raw)
    return parsed


def _parse_case(value: object) -> IntakeEvalCase:
    if not isinstance(value, dict):
        raise IntakeEvaluationError("Each intake evaluation case must be an object.")
    strings = ("id", "category", "name", "goal", "level", "expected_decision", "notes")
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in strings if key != "goal"):
        raise IntakeEvaluationError("Case required text fields are missing.")
    if not isinstance(value.get("goal"), str):
        raise IntakeEvaluationError("Case goal must be a string.")
    if not isinstance(value.get("core"), bool) or value.get("expected_decision") not in {"clear", "clarify"}:
        raise IntakeEvaluationError("Case core or expected_decision is invalid.")
    topics = value.get("required_topics")
    if not isinstance(topics, list) or any(not isinstance(topic, str) or not topic.strip() for topic in topics):
        raise IntakeEvaluationError("Case required_topics must be a list of text.")
    if value["expected_decision"] == "clear" and topics:
        raise IntakeEvaluationError("Clear cases cannot require clarification topics.")
    offline_payload = value.get("offline_payload")
    if not isinstance(offline_payload, dict):
        raise IntakeEvaluationError("Case offline_payload must be an object.")
    return IntakeEvalCase(
        id=value["id"].strip(),
        core=value["core"],
        category=value["category"].strip(),
        name=value["name"].strip(),
        goal=value["goal"].strip(),
        level=value["level"].strip(),
        expected_decision=value["expected_decision"],
        required_topics=tuple(topic.strip() for topic in topics),
        notes=value["notes"].strip(),
        offline_payload=offline_payload,
    )


def _assessment_checks(
    case: IntakeEvalCase,
    assessment: IntakeAssessment,
    *,
    status: str,
) -> dict[str, bool]:
    clarify = assessment.needs_clarification
    structure_valid = _clarify_structure_valid(assessment) if clarify else _clear_structure_valid(assessment, case)
    topic_text = _normalize(
        " ".join(
            item
            for option in assessment.options
            for item in (option.get("label", ""), option.get("description", ""), option.get("scope", ""))
        )
    )
    topic_coverage = not case.required_topics or all(_normalize(topic) in topic_text for topic in case.required_topics)
    fallback_safe = status != "fallback" or assessment.default_scope == case.name
    return {
        "assessment_available": status == "assessed",
        "decision_match": assessment.decision == case.expected_decision,
        "structure_valid": structure_valid,
        "topic_coverage": topic_coverage,
        "sensitive_content_safe": not _contains_sensitive(assessment),
        "fallback_safe": fallback_safe,
    }


def _clear_structure_valid(assessment: IntakeAssessment, case: IntakeEvalCase) -> bool:
    return (
        not assessment.question
        and not assessment.options
        and not assessment.recommended_option
        and assessment.default_scope == case.name
    )


def _clarify_structure_valid(assessment: IntakeAssessment) -> bool:
    options = assessment.options
    values = [option.get("value") for option in options]
    scopes = [option.get("scope") for option in options]
    selected = next((option for option in options if option.get("value") == assessment.recommended_option), None)
    return (
        bool(assessment.question)
        and 2 <= len(options) <= 3
        and all(isinstance(value, str) and value for value in values)
        and len(set(values)) == len(values)
        and all(isinstance(scope, str) and scope for scope in scopes)
        and len(set(scopes)) == len(scopes)
        and selected is not None
        and selected.get("scope") == assessment.default_scope
    )


def _contains_sensitive(assessment: IntakeAssessment) -> bool:
    content = [assessment.reason, assessment.understanding, assessment.question, assessment.default_scope]
    content.extend(assessment.assumptions)
    content.extend(
        value
        for option in assessment.options
        for value in (option.get("label", ""), option.get("description", ""), option.get("scope", ""))
    )
    lowered = " ".join(content).casefold()
    return any(token in lowered for token in ("api key", "authorization", "password", "secret", "密码", "密钥", "访问令牌"))


def _metrics(results: tuple[IntakeEvalResult, ...]) -> dict[str, float | int]:
    total = len(results)
    expected_clear = [result for result in results if result.expected_decision == "clear"]
    expected_clarify = [result for result in results if result.expected_decision == "clarify"]
    clarification_results = [result for result in results if result.actual_decision == "clarify"]
    topic_denominator = [result for result in clarification_results if result.expected_decision == "clarify"]
    fallbacks = [result for result in results if result.status == "fallback"]
    return {
        "total_cases": total,
        "core_cases": sum(result.core for result in results),
        "passed_cases": sum(result.passed for result in results),
        "assessment_availability_rate": _rate(
            sum(result.checks["assessment_available"] for result in results), total
        ),
        "decision_accuracy": _rate(sum(result.checks["decision_match"] for result in results), total),
        "false_interrupt_rate": _rate(
            sum(result.actual_decision == "clarify" for result in expected_clear), len(expected_clear)
        ),
        "false_pass_rate": _rate(
            sum(result.actual_decision != "clarify" for result in expected_clarify), len(expected_clarify)
        ),
        "clarification_structure_rate": _rate(
            sum(result.checks["structure_valid"] for result in clarification_results), len(clarification_results)
        ),
        "topic_coverage_rate": _rate(
            sum(result.checks["topic_coverage"] for result in topic_denominator), len(topic_denominator)
        ),
        "fallback_count": len(fallbacks),
        "fallback_safe_rate": _rate(sum(result.checks["fallback_safe"] for result in fallbacks), len(fallbacks)),
    }


def _quality_gate(
    case_set: IntakeEvalCaseSet,
    results: tuple[IntakeEvalResult, ...],
    metrics: dict[str, float | int],
) -> tuple[bool, list[str]]:
    failures = [f"core:{result.case_id}" for result in results if result.core and not result.passed]
    gate = case_set.quality_gate
    if metrics["decision_accuracy"] < gate["min_decision_accuracy"]:
        failures.append("decision_accuracy")
    if metrics["clarification_structure_rate"] < gate["require_clarification_structure_rate"]:
        failures.append("clarification_structure_rate")
    if metrics["topic_coverage_rate"] < gate["min_topic_coverage_rate"]:
        failures.append("topic_coverage_rate")
    return not failures, failures


def _rate(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _normalize(value: str) -> str:
    return "".join(value.casefold().split())
