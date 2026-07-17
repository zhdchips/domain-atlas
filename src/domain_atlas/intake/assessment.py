"""Deterministic project-intake assessment with an optional future LLM boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_GOAL = "建立可溯源的入门领域地图"


class IntakeSuggestionProvider(Protocol):
    """Optional enhancer that may improve copy, never intake control flow."""

    def suggest(
        self,
        *,
        name: str,
        goal: str,
        level: str,
        assessment: "IntakeAssessment",
    ) -> "IntakeSuggestion | None":
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

    def to_metadata(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "understanding": self.understanding,
            "question": self.question,
            "options": self.options,
            "default_scope": self.default_scope,
            "assumptions": self.assumptions,
        }


@dataclass(frozen=True)
class IntakeSuggestion:
    understanding: str
    question: str
    options: list[dict[str, str]]
    default_scope: str
    assumptions: list[str]


def assess_project_intake(*, name: str, goal: str, level: str) -> IntakeAssessment:
    """Return at most one high-value clarification for a project request."""
    clean_name = name.strip()
    clean_goal = goal.strip()
    normalized_name = clean_name.casefold()
    assumptions = [
        "后续会以该范围决定检索关键词、候选资料筛选和课程组织。",
    ]
    if not clean_goal:
        assumptions.insert(0, f"未填写学习目标，已采用默认目标：{DEFAULT_GOAL}。")

    ambiguous = _ambiguous_assessment(clean_name, normalized_name, assumptions)
    if ambiguous is not None:
        return ambiguous
    broad = _broad_assessment(clean_name, normalized_name, assumptions)
    if broad is not None:
        return broad
    conflict = _level_conflict_assessment(clean_name, clean_goal, level, assumptions)
    if conflict is not None:
        return conflict
    return IntakeAssessment(
        needs_clarification=False,
        reason="clear",
        understanding=f"将围绕“{clean_name}”建立领域地图。",
        question="",
        options=[],
        default_scope=clean_name,
        assumptions=assumptions,
    )


def validate_suggestion_payload(
    payload: object,
    *,
    assessment: IntakeAssessment,
    domain_name: str = "",
) -> IntakeSuggestion | None:
    """Accept only a bounded presentation overlay over rule-owned choices."""
    if not isinstance(payload, dict) or not assessment.needs_clarification:
        return None
    understanding = _safe_text(payload.get("understanding"), max_chars=280)
    question = _safe_text(payload.get("question"), max_chars=120)
    if not understanding or not question:
        return None
    normalized_domain = "".join(domain_name.casefold().split())
    suggestion_text = "".join(f"{understanding} {question}".casefold().split())
    if normalized_domain and normalized_domain not in suggestion_text:
        return None
    allowed_options = {
        option.get("value"): option
        for option in assessment.options
        if option.get("value") and option.get("scope")
    }
    raw_options = payload.get("options")
    if not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 3:
        return None
    options: list[dict[str, str]] = []
    seen_values: set[str] = set()
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            return None
        value = raw_option.get("value")
        baseline = allowed_options.get(value)
        label = _safe_text(raw_option.get("label"), max_chars=60)
        description = _safe_text(raw_option.get("description"), max_chars=160)
        scope = _safe_text(raw_option.get("scope"), max_chars=180)
        if (
            baseline is None
            or value in seen_values
            or not label
            or not description
            or scope != baseline["scope"]
        ):
            return None
        options.append(
            {
                "value": value,
                "label": label,
                "description": description,
                "scope": baseline["scope"],
            }
        )
        seen_values.add(value)
    default_scope = _safe_text(payload.get("default_scope"), max_chars=180)
    if default_scope != assessment.default_scope:
        return None
    assumptions = _safe_text_list(payload.get("assumptions"), max_items=3, max_chars=160)
    if assumptions is None:
        return None
    return IntakeSuggestion(
        understanding=understanding,
        question=question,
        options=options,
        default_scope=default_scope,
        assumptions=assumptions,
    )


def apply_suggestion(assessment: IntakeAssessment, suggestion: IntakeSuggestion) -> IntakeAssessment:
    """Merge a validated overlay while preserving rule-owned fields and mappings."""
    baseline_by_value = {option["value"]: option for option in assessment.options}
    options = [
        {
            **baseline_by_value[item["value"]],
            "label": item["label"],
            "description": item["description"],
        }
        for item in suggestion.options
    ]
    return IntakeAssessment(
        needs_clarification=assessment.needs_clarification,
        reason=assessment.reason,
        understanding=suggestion.understanding,
        question=suggestion.question,
        options=options,
        default_scope=assessment.default_scope,
        assumptions=[*assessment.assumptions, *suggestion.assumptions],
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
        assumptions.append("已按系统当前默认理解继续。")
    else:
        assumptions.append("已采用推荐的领域切入面。")
    metadata.update(
        {
            "confirmed_scope": scope,
            "selection": selection,
            "assumptions": assumptions,
        }
    )
    return metadata


def select_scope(
    assessment: IntakeAssessment,
    *,
    selection: str,
    custom_scope: str,
) -> tuple[str, str | None]:
    """Resolve form input to a scope and optionally a corrected learner level."""
    if custom_scope.strip():
        return custom_scope.strip(), None
    if selection != "default":
        for option in assessment.options:
            if option.get("value") == selection:
                return option["scope"], option.get("level") or None
    return assessment.default_scope, None


def assessment_from_metadata(value: dict[str, Any]) -> IntakeAssessment:
    options = value.get("options") if isinstance(value.get("options"), list) else []
    return IntakeAssessment(
        needs_clarification=True,
        reason=str(value.get("reason") or "needs_clarification"),
        understanding=str(value.get("understanding") or "需要确认领域边界。"),
        question=str(value.get("question") or "你希望优先学习哪个切入面？"),
        options=[item for item in options if isinstance(item, dict)],
        default_scope=str(value.get("default_scope") or ""),
        assumptions=[str(item) for item in value.get("assumptions", []) if str(item).strip()],
    )


def resolved_goal(goal: str) -> str:
    return goal.strip() or DEFAULT_GOAL


def _safe_text(value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or len(text) > max_chars:
        return ""
    lowered = text.casefold()
    if any(token in lowered for token in ("api key", "authorization", "password", "secret")):
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


def _ambiguous_assessment(
    name: str,
    normalized_name: str,
    assumptions: list[str],
) -> IntakeAssessment | None:
    if normalized_name not in {"agent", "agents", "智能体"}:
        return None
    return IntakeAssessment(
        needs_clarification=True,
        reason="ambiguous_domain",
        understanding="“Agent”可能指 LLM Agent、智能体理论，或某个具体框架/产品。",
        question="你希望从哪个角度学习 Agent？",
        options=[
            {"value": "llm_agent", "label": "LLM Agent", "description": "关注工具调用、规划、记忆和评估。", "scope": "LLM Agent：规划、工具调用、记忆与评估"},
            {"value": "agent_theory", "label": "智能体理论", "description": "关注感知、决策、强化学习与多智能体系统。", "scope": "智能体理论：感知、决策、学习与多智能体系统"},
            {"value": "agent_framework", "label": "框架或产品", "description": "关注指定框架、平台或产品的实践。", "scope": "Agent 框架与产品实践"},
        ],
        default_scope="LLM Agent：规划、工具调用、记忆与评估",
        assumptions=assumptions,
    )


def _broad_assessment(
    name: str,
    normalized_name: str,
    assumptions: list[str],
) -> IntakeAssessment | None:
    if normalized_name not in {"ai", "人工智能", "machine learning", "机器学习"}:
        return None
    return IntakeAssessment(
        needs_clarification=True,
        reason="broad_domain",
        understanding=f"“{name}”覆盖多个分支，直接检索会得到过宽且难以组织的资料集合。",
        question="你想先从哪个切入面建立领域地图？",
        options=[
            {"value": "fundamentals", "label": "基础原理", "description": "模型、学习范式、数学基础与核心概念。", "scope": f"{name} 基础原理：核心概念、学习范式与模型"},
            {"value": "engineering", "label": "工程应用", "description": "数据、训练、部署、评估与系统实践。", "scope": f"{name} 工程应用：数据、训练、部署与评估"},
            {"value": "industry", "label": "特定行业", "description": "以行业场景、案例、约束与最佳实践组织。", "scope": f"{name} 行业应用与案例"},
        ],
        default_scope=f"{name} 基础原理：核心概念、学习范式与模型",
        assumptions=assumptions,
    )


def _level_conflict_assessment(
    name: str,
    goal: str,
    level: str,
    assumptions: list[str],
) -> IntakeAssessment | None:
    normalized_goal = goal.casefold()
    level = level.strip().lower()
    advanced_signals = ("高级", "专家", "前沿研究", "论文复现")
    beginner_signals = ("从零", "零基础", "入门")
    if level == "beginner" and any(signal in normalized_goal for signal in advanced_signals):
        return _conflict_assessment(name, assumptions, "advanced", "你的目标偏进阶，但当前水平选择为入门。")
    if level == "advanced" and any(signal in normalized_goal for signal in beginner_signals):
        return _conflict_assessment(name, assumptions, "beginner", "你的目标是从基础开始，但当前水平选择为进阶。")
    return None


def _conflict_assessment(
    name: str,
    assumptions: list[str],
    recommended_level: str,
    understanding: str,
) -> IntakeAssessment:
    level_label = {"beginner": "入门", "intermediate": "有基础", "advanced": "进阶"}
    return IntakeAssessment(
        needs_clarification=True,
        reason="level_goal_conflict",
        understanding=understanding,
        question="你希望优先调整学习目标，还是调整当前水平？",
        options=[
            {"value": "align_level", "label": f"调整为{level_label[recommended_level]}", "description": "保留当前学习目标，并按匹配的深度组织课程。", "scope": name, "level": recommended_level},
            {"value": "keep_level", "label": "保留当前水平", "description": "系统会将学习目标解释为循序渐进的长期方向。", "scope": name},
        ],
        default_scope=name,
        assumptions=assumptions,
    )
