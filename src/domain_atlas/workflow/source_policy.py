"""Deterministic source assessment and guided-selection policy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from urllib.parse import urlparse, urlunparse

from domain_atlas.domain.source_candidates import SourceCandidateDraft


DIRECT_AUTHORITY_ROLES = {"first_party", "primary_document"}
PREFERRED_ROLES = {
    "first_party",
    "primary_document",
    "institution",
    "paper",
    "independent_coverage",
    "repository",
    "community_tool",
}
ROLE_ORDER = {
    "first_party": 0,
    "primary_document": 1,
    "institution": 2,
    "paper": 3,
    "independent_coverage": 4,
    "repository": 5,
    "community_tool": 6,
    "unverified": 7,
    "mirror_or_fork": 8,
}
SERVICE_WORKFLOW_MARKERS = (
    "取号",
    "排队",
    "预约",
    "挂号",
    "就餐",
    "办理",
    "服务规则",
    "服务流程",
    "操作流程",
    "小程序",
    "customer service",
    "booking",
    "reservation",
    "queue",
)
TECHNICAL_SCOPE_MARKERS = (
    "开源",
    "代码仓库",
    "仓库",
    "sdk",
    " api",
    "github",
    "repository",
    "repo",
    "工具实现",
    "项目实现",
    "开发",
)
MIRROR_MARKERS = ("fork", "forked from", "镜像", "转载", "mirror")


@dataclass(frozen=True)
class SelectionPlan:
    assessed: list[SourceCandidateDraft]
    queue: list[SourceCandidateDraft]
    requires_direct_authority: bool
    evidence_insufficient_reason: str = ""

    @property
    def policy_name(self) -> str:
        return "official_first" if self.requires_direct_authority else "standard"


def assess_candidates(
    scope: str,
    candidates: list[SourceCandidateDraft],
) -> list[SourceCandidateDraft]:
    """Attach stable source role/family explanations without external calls."""
    assessed = [_assess_candidate(scope, candidate) for candidate in candidates]
    by_family: dict[str, list[SourceCandidateDraft]] = defaultdict(list)
    for candidate in assessed:
        by_family[_metadata_str(candidate, "source_family")].append(candidate)

    result: list[SourceCandidateDraft] = []
    for candidate in assessed:
        family = _metadata_str(candidate, "source_family")
        # Discovery order is the provider's strongest available tie-breaker. Keeping
        # it avoids preferring a fork solely because its account name sorts earlier.
        representative = by_family[family][0]
        if candidate.provider_source_id != representative.provider_source_id:
            metadata = dict(candidate.metadata)
            metadata.update(
                {
                    "source_role": "mirror_or_fork",
                    "duplicate_of": representative.provider_source_id,
                    "selection_reason": (
                        f"与候选“{representative.title}”属于同一来源族，"
                        "不会作为独立证据自动摄取。"
                    ),
                    "manual_warning": "该资料与已有候选存在镜像、fork 或近似来源关系。",
                }
            )
            result.append(replace(candidate, metadata=metadata))
        else:
            result.append(candidate)
    return result


def build_selection_plan(scope: str, candidates: list[SourceCandidateDraft]) -> SelectionPlan:
    """Choose a guided queue, or fail closed when direct evidence is required."""
    assessed = assess_candidates(scope, candidates)
    requires_direct_authority = scope_requires_direct_authority(scope)
    representatives = [
        candidate
        for candidate in assessed
        if not _metadata_str(candidate, "duplicate_of")
    ]
    direct = [
        candidate
        for candidate in representatives
        if _metadata_str(candidate, "source_role") in DIRECT_AUTHORITY_ROLES
    ]
    if requires_direct_authority and not direct:
        return SelectionPlan(
            assessed=assessed,
            queue=[],
            requires_direct_authority=True,
            evidence_insufficient_reason=(
                "该领域涉及品牌或机构服务流程，但未找到可验证的一方或直接权威资料。"
                "已保留第三方候选供手动确认；请补充官方帮助页、公告、服务规则或可访问的原始资料。"
            ),
        )

    eligible = [candidate for candidate in representatives if _is_guided_eligible(scope, candidate)]
    ranked = sorted(eligible, key=_rank_key)
    queue = _apply_domain_cap(ranked)
    return SelectionPlan(
        assessed=assessed,
        queue=queue,
        requires_direct_authority=requires_direct_authority,
    )


def scope_requires_direct_authority(scope: str) -> bool:
    normalized = scope.lower().strip()
    if not normalized or any(marker in normalized for marker in TECHNICAL_SCOPE_MARKERS):
        return False
    return any(marker in normalized for marker in SERVICE_WORKFLOW_MARKERS)


def candidate_metadata(candidate: SourceCandidateDraft) -> dict[str, object]:
    return dict(candidate.metadata)


def _assess_candidate(scope: str, candidate: SourceCandidateDraft) -> SourceCandidateDraft:
    metadata = dict(candidate.metadata)
    role = _source_role(candidate)
    family = _source_family(candidate)
    direct = role in DIRECT_AUTHORITY_ROLES
    technical_scope = not scope_requires_direct_authority(scope) and any(
        marker in scope.lower() for marker in TECHNICAL_SCOPE_MARKERS
    )
    if role == "repository" and technical_scope:
        reason = "代码仓库与当前开源/工具范围直接相关，可作为主资料候选。"
        warning = ""
    elif role == "repository":
        reason = "代码仓库是第三方技术资料；对品牌或服务流程仅作补充，不是官方流程证据。"
        warning = "该代码仓库不是官方服务流程证据，请优先确认官方资料。"
    elif direct:
        reason = "具备直接文档信号，可作为自动构建的一方或直接权威资料候选。"
        warning = ""
    elif role == "institution":
        reason = "机构资料可提供独立背景证据，但不替代服务运营方的官方规则。"
        warning = ""
    elif role == "mirror_or_fork":
        reason = "该资料与其他候选属于同一来源族。"
        warning = ""
    else:
        reason = "该资料可提供补充信息，自动构建时会与直接资料和独立来源一起评估。"
        warning = ""
    metadata.update(
        {
            "source_role": role,
            "source_family": family,
            "is_direct_authority": direct,
            "selection_reason": reason,
            "manual_warning": warning,
        }
    )
    return replace(candidate, metadata=metadata)


def _source_role(candidate: SourceCandidateDraft) -> str:
    hinted = _metadata_str(candidate, "source_role")
    if hinted in ROLE_ORDER:
        return hinted
    combined = f"{candidate.title} {candidate.snippet}".lower()
    if candidate.source_type == "official_docs":
        return "primary_document"
    if candidate.source_type == "institution":
        return "institution"
    if candidate.source_type == "paper":
        return "paper"
    if candidate.source_type == "repository":
        return "repository"
    if candidate.source_type == "encyclopedia":
        return "independent_coverage"
    if any(marker in combined for marker in MIRROR_MARKERS):
        return "mirror_or_fork"
    if candidate.source_type == "web":
        return "independent_coverage"
    return "unverified"


def _source_family(candidate: SourceCandidateDraft) -> str:
    explicit = _metadata_str(candidate, "source_family")
    if explicit:
        return explicit
    parsed = urlparse(candidate.url)
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part.lower() for part in parsed.path.split("/") if part]
    if host == "github.com" and parts:
        # Repository names are intentionally grouped across owners: forks otherwise
        # frequently look like independent evidence before their README is fetched.
        return f"github-repository:{parts[-1]}"
    canonical = urlunparse((parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", "", ""))
    return canonical or candidate.url.rstrip("/").lower()


def _is_guided_eligible(scope: str, candidate: SourceCandidateDraft) -> bool:
    role = _metadata_str(candidate, "source_role")
    if role not in PREFERRED_ROLES:
        return False
    if role in {"repository", "community_tool"} and scope_requires_direct_authority(scope):
        return False
    return candidate.authority_score >= 0.5 or role in DIRECT_AUTHORITY_ROLES


def _rank_key(candidate: SourceCandidateDraft) -> tuple[int, float, str]:
    return (
        ROLE_ORDER.get(_metadata_str(candidate, "source_role"), len(ROLE_ORDER)),
        -candidate.authority_score,
        candidate.title.lower(),
    )


def _apply_domain_cap(
    candidates: list[SourceCandidateDraft], *, max_per_domain: int = 2
) -> list[SourceCandidateDraft]:
    domain_counts: dict[str, int] = defaultdict(int)
    selected: list[SourceCandidateDraft] = []
    for candidate in candidates:
        domain = urlparse(candidate.url).netloc.lower()
        if domain_counts[domain] >= max_per_domain:
            continue
        selected.append(candidate)
        domain_counts[domain] += 1
    return selected


def _metadata_str(candidate: SourceCandidateDraft, key: str) -> str:
    value = candidate.metadata.get(key)
    return value.strip() if isinstance(value, str) else ""
