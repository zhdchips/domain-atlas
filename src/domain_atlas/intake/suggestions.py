"""LLM implementation for constrained intake copy suggestions."""

from __future__ import annotations

import json
from typing import Any, Protocol

from domain_atlas.intake.assessment import (
    IntakeAssessment,
    IntakeSuggestion,
    validate_suggestion_payload,
)


class ChatProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...


class LLMIntakeSuggestionProvider:
    """Use one chat completion to improve an already-required clarification."""

    def __init__(self, chat_provider: ChatProvider) -> None:
        self.chat_provider = chat_provider

    def suggest(
        self,
        *,
        name: str,
        goal: str,
        level: str,
        assessment: IntakeAssessment,
    ) -> IntakeSuggestion | None:
        payload = self.chat_provider.complete_json(
            system_prompt=_system_prompt(),
            user_prompt=_user_prompt(
                name=name,
                goal=goal,
                level=level,
                assessment=assessment,
            ),
        )
        return validate_suggestion_payload(payload, assessment=assessment, domain_name=name)


def _system_prompt() -> str:
    return (
        "You improve the wording of a Domain Atlas clarification that local rules have already "
        "decided is necessary. Return strict JSON only. Do not decide whether clarification is "
        "needed, do not add options, do not change option values, scopes, or learner level. "
        "Keep Chinese copy concise, neutral, and directly useful."
    )


def _user_prompt(*, name: str, goal: str, level: str, assessment: IntakeAssessment) -> str:
    allowed_options = [
        {
            "value": option.get("value"),
            "scope": option.get("scope"),
            "level": option.get("level"),
        }
        for option in assessment.options
    ]
    contract = {
        "understanding": "string, <= 280 chars, must mention the domain",
        "question": "one string, <= 120 chars",
        "options": [
            {
                "value": "must be one allowed value",
                "label": "string <= 60 chars",
                "description": "string <= 160 chars",
                "scope": "must exactly equal the matching allowed scope",
            }
        ],
        "default_scope": "must exactly equal the rule default scope",
        "assumptions": ["optional strings <= 160 chars, at most 3"],
    }
    return (
        "Improve this existing clarification without changing its control boundary.\n"
        f"Domain: {name}\nGoal: {goal or '未填写'}\nLevel: {level}\n"
        f"Rule reason: {assessment.reason}\n"
        f"Rule understanding: {assessment.understanding}\n"
        f"Rule question: {assessment.question}\n"
        f"Allowed options: {json.dumps(allowed_options, ensure_ascii=False)}\n"
        f"Rule default scope: {assessment.default_scope}\n"
        f"Required JSON contract: {json.dumps(contract, ensure_ascii=False)}"
    )
