from __future__ import annotations

import pytest

from domain_atlas.intake.assessment import (
    DEFAULT_GOAL,
    fallback_intake_assessment,
    resolved_goal,
    select_scope,
    validate_assessment_payload,
)


def test_fallback_intake_creates_directly_and_defaults_missing_goal():
    assessment = fallback_intake_assessment(name="Dataphin", goal="", level="beginner")

    assert assessment.needs_clarification is False
    assert assessment.reason == "assessment_unavailable"
    assert assessment.default_scope == "Dataphin"
    assert DEFAULT_GOAL in assessment.assumptions[0]
    assert resolved_goal("") == DEFAULT_GOAL


def test_valid_clear_assessment_preserves_submitted_domain_scope():
    assessment = validate_assessment_payload(_clear_payload("Dataphin"), domain_name="Dataphin")

    assert assessment is not None
    assert assessment.decision == "clear"
    assert assessment.default_scope == "Dataphin"
    assert assessment.options == []


@pytest.mark.parametrize("domain_name", ["Agent", "数据治理", "产品运营"])
def test_valid_clarification_has_one_question_and_user_selectable_scopes(domain_name):
    assessment = validate_assessment_payload(_clarify_payload(domain_name), domain_name=domain_name)

    assert assessment is not None
    assert assessment.decision == "clarify"
    assert assessment.recommended_option == "foundations"
    assert len(assessment.options) == 2
    scope, level = select_scope(assessment, selection="practice", custom_scope="")
    assert scope.endswith("实践")
    assert level is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"confidence": 1.1}),
        lambda payload: payload.update({"options": payload["options"][:1]}),
        lambda payload: payload["options"][1].update({"value": "foundations"}),
        lambda payload: payload.update({"recommended_option": "missing"}),
        lambda payload: payload.update({"default_scope": "错误范围"}),
        lambda payload: payload["options"][0].update({"scope": "api key=should-not-appear"}),
        lambda payload: payload.update({"understanding": "这是一个宽泛领域"}),
    ],
)
def test_invalid_llm_assessment_payload_is_rejected(mutate):
    payload = _clarify_payload("数据治理")
    mutate(payload)

    assert validate_assessment_payload(payload, domain_name="数据治理") is None


def _clear_payload(name: str) -> dict[str, object]:
    return {
        "decision": "clear",
        "confidence": 0.91,
        "reason": "目标和领域边界足以开始构建。",
        "understanding": f"将围绕{name}的入门学习建立领域地图。",
        "question": "",
        "options": [],
        "recommended_option": "",
        "default_scope": name,
        "assumptions": ["先以提交的领域名称作为检索边界。"],
    }


def _clarify_payload(name: str) -> dict[str, object]:
    return {
        "decision": "clarify",
        "confidence": 0.86,
        "reason": "领域覆盖多个常见学习切入面。",
        "understanding": f"“{name}”可以从方法基础或落地实践进入。",
        "question": f"你希望优先从{name}的哪个切入面学习？",
        "options": [
            {
                "value": "foundations",
                "label": "方法基础",
                "description": "先理解核心概念、方法论与关键流程。",
                "scope": f"{name} 方法基础",
            },
            {
                "value": "practice",
                "label": "落地实践",
                "description": "围绕组织落地、案例与实践方法学习。",
                "scope": f"{name} 落地实践",
            },
        ],
        "recommended_option": "foundations",
        "default_scope": f"{name} 方法基础",
        "assumptions": ["后续资料筛选将以确认后的范围为准。"],
    }
