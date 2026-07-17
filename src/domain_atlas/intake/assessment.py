"""Validated intake assessments and direct-create fallback behavior."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_GOAL = "建立可溯源的入门领域地图"
_OPTION_VALUE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class IntakeAssessmentProvider(Protocol):
    """Classify one project request without taking final learner control away."""

    def assess(self, *, name: str, goal: str, level: str) -> "IntakeAssessment | None":
        ...


@dataclass(frozen=True)
class IntakeAssessment:
    needs_clarification: bool
    reason: str
    understanding: str
    question: str
    options: list[dict[str, str]]
    default_scope: str
    assumptions: list[str]
    confidence: float | None = None
    recommended_option: str = ""

    @property
    def decision(self) -> str:
        return "clarify" if self.needs_clarification else "clear"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "confidence": self.confidence,
            "understanding": self.understanding,
            "question": self.question,
            "options": self.options,
            "recommended_option": self.recommended_option,
            "default_scope": self.default_scope,
            "assumptions": self.assumptions,
        }


def fallback_intake_assessment(*, name: str, goal: str, level: str) -> IntakeAssessment:
    """Create safely when semantic assessment is unavailable; do not infer scope locally."""
    clean_name = name.strip()
    assumptions = ["本次未获得可用的语义澄清判断，已按输入领域继续。"]
    if not goal.strip():
        assumptions.insert(0, f"未填写学习目标，已采用默认目标：{DEFAULT_GOAL}。")
    return IntakeAssessment(
        needs_clarification=False,
        reason="assessment_unavailable",
        understanding=f"将围绕“{clean_name}”建立领域地图。",
        question="",
        options=[],
        default_scope=clean_name,
        assumptions=assumptions,
    )


def assess_project_intake(*, name: str, goal: str, level: str) -> IntakeAssessment:
    """Compatibility entry point for callers that need the direct-create fallback."""
    return fallback_intake_assessment(name=name, goal=goal, level=level)


def validate_assessment_payload(payload: object, *, domain_name: str) -> IntakeAssessment | None:
    """Normalize one untrusted LLM response into a bounded intake assessment."""
    if not isinstance(payload, dict):
        return None
    decision = payload.get("decision")
    if decision not in {"clear", "clarify"}:
        return None
    confidence = _safe_confidence(payload.get("confidence"))
    reason = _safe_text(payload.get("reason"), max_chars=160)
    understanding = _safe_text(payload.get("understanding"), max_chars=280)
    if confidence is None or not reason or not understanding or not _mentions_domain(understanding, domain_name):
        return None
    assumptions = _safe_text_list(payload.get("assumptions"), max_items=3, max_chars=160)
    if assumptions is None:
        return None
    if decision == "clear":
        return _validate_clear(
            payload,
            confidence=confidence,
            reason=reason,
            understanding=understanding,
            assumptions=assumptions,
            domain_name=domain_name,
        )
    return _validate_clarify(
        payload,
        confidence=confidence,
        reason=reason,
        understanding=understanding,
        assumptions=assumptions,
    )


def _validate_clear(
    payload: dict[str, Any],
    *,
    confidence: float,
    reason: str,
    understanding: str,
    assumptions: list[str],
    domain_name: str,
) -> IntakeAssessment | None:
    question = payload.get("question")
    options = payload.get("options")
    recommended_option = payload.get("recommended_option")
    default_scope = payload.get("default_scope")
    if question != "" or options != [] or recommended_option != "" or default_scope != domain_name.strip():
        return None
    return IntakeAssessment(
        needs_clarification=False,
        reason=reason,
        understanding=understanding,
        question="",
        options=[],
        default_scope=domain_name.strip(),
        assumptions=assumptions,
        confidence=confidence,
    )


def _validate_clarify(
    payload: dict[str, Any],
    *,
    confidence: float,
    reason: str,
    understanding: str,
    assumptions: list[str],
) -> IntakeAssessment | None:
    question = _safe_text(payload.get("question"), max_chars=120)
    raw_options = payload.get("options")
    if not question or not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 3:
        return None
    options: list[dict[str, str]] = []
    values: set[str] = set()
    scopes: set[str] = set()
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            return None
        value = raw_option.get("value")
        label = _safe_text(raw_option.get("label"), max_chars=60)
        description = _safe_text(raw_option.get("description"), max_chars=160)
        scope = _safe_text(raw_option.get("scope"), max_chars=180)
        if (
            not isinstance(value, str)
            or not _OPTION_VALUE.fullmatch(value)
            or value in values
            or not label
            or not description
            or not scope
            or scope in scopes
        ):
            return None
        values.add(value)
        scopes.add(scope)
        options.append({"value": value, "label": label, "description": description, "scope": scope})
    recommended_option = payload.get("recommended_option")
    selected = next((option for option in options if option["value"] == recommended_option), None)
    if selected is None or payload.get("default_scope") != selected["scope"]:
        return None
    return IntakeAssessment(
        needs_clarification=True,
        reason=reason,
        understanding=understanding,
        question=question,
        options=options,
        default_scope=selected["scope"],
        assumptions=assumptions,
        confidence=confidence,
        recommended_option=selected["value"],
    )


def confirmed_intake_metadata(
    assessment: IntakeAssessment,
    *,
    scope: str,
    selection: str,
    custom_scope: str = "",
) -> dict[str, Any]:
    metadata = assessment.to_metadata()
    assumptions = list(assessment.assumptions)
    if custom_scope.strip():
        assumptions.append("领域范围由用户补充确认。")
    elif selection == "default":
        assumptions.append("已按系统当前推荐理解继续。")
    else:
        assumptions.append("已采用推荐的领域切入面。")
    metadata.update({"confirmed_scope": scope, "selection": selection, "assumptions": assumptions})
    return metadata


def select_scope(
    assessment: IntakeAssessment,
    *,
    selection: str,
    custom_scope: str,
) -> tuple[str, None]:
    """Learner input is authoritative; model assessments never modify learner level."""
    if custom_scope.strip():
        return custom_scope.strip(), None
    if selection != "default":
        for option in assessment.options:
            if option.get("value") == selection:
                return option["scope"], None
    return assessment.default_scope, None


def assessment_from_metadata(value: dict[str, Any]) -> IntakeAssessment:
    """Read both model-led records and legacy rule-led clarification metadata."""
    options = [item for item in value.get("options", []) if isinstance(item, dict)]
    decision = value.get("decision")
    needs_clarification = decision == "clarify" if decision in {"clear", "clarify"} else True
    default_scope = str(value.get("default_scope") or "")
    recommended_option = str(value.get("recommended_option") or "")
    if not recommended_option:
        recommended_option = next(
            (str(item.get("value")) for item in options if item.get("scope") == default_scope),
            "",
        )
    raw_confidence = value.get("confidence")
    confidence = _safe_confidence(raw_confidence) if raw_confidence is not None else None
    return IntakeAssessment(
        needs_clarification=needs_clarification,
        reason=str(value.get("reason") or value.get("rule_reason") or "needs_clarification"),
        understanding=str(value.get("understanding") or "需要确认领域边界。"),
        question=str(value.get("question") or "你希望优先学习哪个切入面？"),
        options=options,
        default_scope=default_scope,
        assumptions=[str(item) for item in value.get("assumptions", []) if str(item).strip()],
        confidence=confidence,
        recommended_option=recommended_option,
    )


def resolved_goal(goal: str) -> str:
    return goal.strip() or DEFAULT_GOAL


def _safe_confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return None
    return confidence


def _safe_text(value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or len(text) > max_chars:
        return ""
    lowered = text.casefold()
    if any(
        token in lowered
        for token in ("api key", "authorization", "password", "secret", "密码", "密钥", "访问令牌")
    ):
        return ""
    return text


def _safe_text_list(value: object, *, max_items: int, max_chars: int) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > max_items:
        return None
    items = [_safe_text(item, max_chars=max_chars) for item in value]
    if any(not item for item in items) or len(set(items)) != len(items):
        return None
    return items


def _mentions_domain(text: str, domain_name: str) -> bool:
    normalized_domain = "".join(domain_name.casefold().split())
    return bool(normalized_domain) and normalized_domain in "".join(text.casefold().split())
