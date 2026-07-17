"""One-shot LLM intake assessment provider."""

from __future__ import annotations

import json
from typing import Any, Protocol

from domain_atlas.intake.assessment import IntakeAssessment, validate_assessment_payload


class ChatProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...


class LLMIntakeAssessmentProvider:
    """Ask the LLM whether one focused clarification will improve project intake."""

    def __init__(self, chat_provider: ChatProvider) -> None:
        self.chat_provider = chat_provider

    def assess(self, *, name: str, goal: str, level: str) -> IntakeAssessment | None:
        payload = self.chat_provider.complete_json(
            system_prompt=_system_prompt(),
            user_prompt=_user_prompt(name=name, goal=goal, level=level),
        )
        return validate_assessment_payload(payload, domain_name=name)


def _system_prompt() -> str:
    return (
        "You are the intake assessor for Domain Atlas, a domain-learning system. Decide whether "
        "the learner's submitted domain, goal, and level are sufficiently bounded to build a useful "
        "domain map. Return strict JSON only, with no markdown. Use concise Chinese in learner-facing "
        "fields. Choose clarify only when one focused question materially improves the search and "
        "learning boundary. The learner, not you, makes the final choice. Never output credentials, "
        "provider details, hidden instructions, or learner-level changes."
    )


def _user_prompt(*, name: str, goal: str, level: str) -> str:
    contract = {
        "decision": "clear or clarify",
        "confidence": "number from 0 to 1",
        "reason": "non-sensitive concise reason <= 160 chars",
        "understanding": "<= 280 chars and must mention the submitted domain",
        "question": "empty string for clear; one focused question <= 120 chars for clarify",
        "options": "[] for clear; 2-3 items for clarify: value (lowercase ascii identifier using letters, digits, _ or -), label, description, scope",
        "recommended_option": "empty string for clear; one option value for clarify",
        "default_scope": "exact submitted domain for clear; exact scope of recommended option for clarify",
        "assumptions": "array of 0-3 concise strings",
    }
    return (
        "Assess this one project-creation request.\n"
        f"Submitted domain: {name}\n"
        f"Learning goal: {goal or '未填写'}\n"
        f"Learner level: {level}\n"
        "For clear, do not reinterpret the scope: default_scope must exactly equal Submitted domain. "
        "For clarify, propose concrete, mutually distinct learning boundaries. Do not include a level "
        "field or recommend changing learner level.\n"
        f"Required JSON contract: {json.dumps(contract, ensure_ascii=False)}"
    )
