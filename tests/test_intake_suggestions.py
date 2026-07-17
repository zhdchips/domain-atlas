from __future__ import annotations

import pytest

from domain_atlas.intake.assessment import assess_project_intake
from domain_atlas.intake.suggestions import LLMIntakeSuggestionProvider


class FakeChatProvider:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def complete_json(self, *, system_prompt: str, user_prompt: str):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_llm_intake_provider_accepts_only_allowed_presentation_overlay():
    assessment = assess_project_intake(name="Agent", goal="学习", level="beginner")
    chat = FakeChatProvider(_valid_payload(assessment))

    suggestion = LLMIntakeSuggestionProvider(chat).suggest(
        name="Agent",
        goal="学习",
        level="beginner",
        assessment=assessment,
    )

    assert chat.calls == 1
    assert suggestion is not None
    assert suggestion.question == "你希望优先掌握哪类 Agent 能力？"
    assert [option["value"] for option in suggestion.options] == ["llm_agent", "agent_theory"]
    assert suggestion.default_scope == assessment.default_scope


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"options": payload["options"][:1]}),
        lambda payload: payload["options"][0].update({"scope": "任意新范围"}),
        lambda payload: payload["options"][0].update({"label": "x" * 61}),
        lambda payload: payload.update({"default_scope": "任意默认范围"}),
        lambda payload: payload.update({"understanding": ""}),
        lambda payload: payload.update({"understanding": "请点击此处获取优惠", "question": "你要继续吗？"}),
    ],
)
def test_llm_intake_provider_rejects_invalid_suggestion_payload(mutate):
    assessment = assess_project_intake(name="Agent", goal="学习", level="beginner")
    payload = _valid_payload(assessment)
    mutate(payload)

    suggestion = LLMIntakeSuggestionProvider(FakeChatProvider(payload)).suggest(
        name="Agent",
        goal="学习",
        level="beginner",
        assessment=assessment,
    )

    assert suggestion is None


def _valid_payload(assessment):
    return {
        "understanding": "Agent 在这里可能指不同的学习方向。",
        "question": "你希望优先掌握哪类 Agent 能力？",
        "options": [
            {
                "value": option["value"],
                "label": f"建议：{option['label']}",
                "description": f"适合从 {option['label']} 开始建立学习边界。",
                "scope": option["scope"],
            }
            for option in assessment.options[:2]
        ],
        "default_scope": assessment.default_scope,
        "assumptions": ["建议会保持在本地规则给出的边界内。"],
    }
