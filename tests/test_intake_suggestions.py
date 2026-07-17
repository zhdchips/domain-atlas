from __future__ import annotations

from domain_atlas.intake.suggestions import LLMIntakeAssessmentProvider


class FakeChatProvider:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def complete_json(self, *, system_prompt: str, user_prompt: str):
        self.calls += 1
        assert "decision" in user_prompt
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_llm_intake_provider_returns_validated_assessment_with_one_completion():
    chat = FakeChatProvider(_valid_payload())

    assessment = LLMIntakeAssessmentProvider(chat).assess(
        name="数据治理",
        goal="建立团队实践地图",
        level="beginner",
    )

    assert chat.calls == 1
    assert assessment is not None
    assert assessment.needs_clarification is True
    assert assessment.default_scope == "数据治理 方法基础"


def test_llm_intake_provider_rejects_invalid_response_without_retry():
    payload = _valid_payload()
    payload["confidence"] = -0.1
    chat = FakeChatProvider(payload)

    assert LLMIntakeAssessmentProvider(chat).assess(name="数据治理", goal="", level="beginner") is None
    assert chat.calls == 1


def _valid_payload() -> dict[str, object]:
    return {
        "decision": "clarify",
        "confidence": 0.86,
        "reason": "领域覆盖多个常见学习切入面。",
        "understanding": "“数据治理”可以从方法基础或落地实践进入。",
        "question": "你希望优先从数据治理的哪个切入面学习？",
        "options": [
            {
                "value": "foundations",
                "label": "方法基础",
                "description": "先理解核心概念、方法论与关键流程。",
                "scope": "数据治理 方法基础",
            },
            {
                "value": "practice",
                "label": "落地实践",
                "description": "围绕组织落地、案例与实践方法学习。",
                "scope": "数据治理 落地实践",
            },
        ],
        "recommended_option": "foundations",
        "default_scope": "数据治理 方法基础",
        "assumptions": [],
    }
