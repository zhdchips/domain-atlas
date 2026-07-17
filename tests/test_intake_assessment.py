from __future__ import annotations

from domain_atlas.intake.assessment import DEFAULT_GOAL, assess_project_intake, resolved_goal, select_scope


def test_clear_intake_does_not_require_clarification_and_defaults_missing_goal():
    assessment = assess_project_intake(
        name="Dataphin",
        goal="",
        level="beginner",
    )

    assert assessment.needs_clarification is False
    assert assessment.reason == "clear"
    assert assessment.default_scope == "Dataphin"
    assert DEFAULT_GOAL in assessment.assumptions[0]
    assert resolved_goal("") == DEFAULT_GOAL


def test_ambiguous_agent_has_one_focused_question_and_recommended_scope():
    assessment = assess_project_intake(name="Agent", goal="学习", level="beginner")

    assert assessment.needs_clarification is True
    assert assessment.reason == "ambiguous_domain"
    assert "哪个角度" in assessment.question
    assert [item["value"] for item in assessment.options] == [
        "llm_agent",
        "agent_theory",
        "agent_framework",
    ]
    scope, level = select_scope(assessment, selection="llm_agent", custom_scope="")
    assert scope.startswith("LLM Agent")
    assert level is None


def test_broad_scope_and_level_goal_conflict_are_explainable():
    broad = assess_project_intake(name="AI", goal="理解", level="beginner")
    conflict = assess_project_intake(name="Dataphin", goal="完成高级论文复现", level="beginner")

    assert broad.reason == "broad_domain"
    assert len(broad.options) == 3
    assert conflict.reason == "level_goal_conflict"
    _, level = select_scope(conflict, selection="align_level", custom_scope="")
    assert level == "advanced"
