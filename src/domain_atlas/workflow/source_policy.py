"""Deterministic source assessment and guided-selection policy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import re
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
REGION_LABELS = {
    "CN": ("中国大陆", "中国", "大陆", "广州", "北京", "上海", "深圳", "成都", "中国内地"),
    "TW": ("台湾", "台灣", "taiwan"),
    "HK": ("香港", "hong kong"),
}
OFFICIAL_PRESENTATION_MARKERS = (
    "欢迎光临",
    "歡迎光臨",
    "官方网站",
    "官方網站",
    "official",
    "官网",
    "官網",
    "首页",
    "首頁",
)
GENERIC_DOMAIN_LABELS = {"www", "com", "net", "org", "co", "cn", "tw", "hk", "nps"}
TRADITIONAL_TO_SIMPLIFIED = str.maketrans({"壽": "寿", "臺": "台", "灣": "湾", "廣": "广", "陸": "陆", "國": "国"})


@dataclass(frozen=True)
class SelectionPlan:
    assessed: list[SourceCandidateDraft]
    queue: list[SourceCandidateDraft]
    requires_direct_authority: bool
    evidence_insufficient_reason: str = ""
    terminal_reason: str = ""

    @property
    def policy_name(self) -> str:
        return "official_first" if self.requires_direct_authority else "standard"


def assess_candidates(
    scope: str,
    candidates: list[SourceCandidateDraft],
    *,
    language: str = "zh",
) -> list[SourceCandidateDraft]:
    """Attach stable source role/family explanations without external calls."""
    target_region = infer_target_region(scope, language=language)
    identity_tokens = _brand_identity_tokens(scope, candidates)
    assessed = [
        _assess_candidate(
            scope,
            candidate,
            target_region=target_region,
            identity_tokens=identity_tokens,
        )
        for candidate in candidates
    ]
    by_family: dict[str, list[SourceCandidateDraft]] = defaultdict(list)
    for candidate in assessed:
        by_family[_metadata_str(candidate, "source_family")].append(candidate)

    result: list[SourceCandidateDraft] = []
    for candidate in assessed:
        family = _metadata_str(candidate, "source_family")
        # Discovery order is the provider's strongest available tie-breaker. Keeping
        # it avoids preferring a fork solely because its account name sorts earlier.
        representative = by_family[family][0]
        if candidate is not representative:
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


def build_selection_plan(
    scope: str,
    candidates: list[SourceCandidateDraft],
    *,
    language: str = "zh",
) -> SelectionPlan:
    """Apply only deterministic evidence and safety gates to guided candidates."""
    assessed = assess_candidates(scope, candidates, language=language)
    requires_direct_authority = scope_requires_direct_authority(scope)
    representatives = [
        candidate
        for candidate in assessed
        if not _metadata_str(candidate, "duplicate_of")
    ]
    direct = [
        candidate
        for candidate in representatives
        if candidate.metadata.get("is_direct_authority") is True
    ]
    if requires_direct_authority and not direct:
        terminal_reason, reason = _official_evidence_gap(assessed)
        return SelectionPlan(
            assessed=assessed,
            queue=[],
            requires_direct_authority=True,
            evidence_insufficient_reason=reason,
            terminal_reason=terminal_reason,
        )

    eligible = [candidate for candidate in representatives if _is_guided_eligible(scope, candidate)]
    ranked = sorted(eligible, key=lambda candidate: _guided_rank_key(scope, candidate))
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


def _assess_candidate(
    scope: str,
    candidate: SourceCandidateDraft,
    *,
    target_region: str,
    identity_tokens: set[str],
) -> SourceCandidateDraft:
    metadata = dict(candidate.metadata)
    llm_assessment = metadata.get("candidate_assessment")
    brand_domain_candidate = _is_brand_domain_candidate(scope, candidate, identity_tokens)
    role = _source_role(candidate, brand_domain_candidate=brand_domain_candidate)
    family = _source_family(candidate)
    source_region = _source_region(candidate)
    region_match = _region_match(target_region, source_region)
    auto_ingestible = metadata.get("auto_ingestible") is not False
    direct = (
        role in DIRECT_AUTHORITY_ROLES
        and region_match != "cross_region"
        and auto_ingestible
    )
    technical_scope = not scope_requires_direct_authority(scope) and any(
        marker in scope.lower() for marker in TECHNICAL_SCOPE_MARKERS
    )
    if region_match == "cross_region" and role in DIRECT_AUTHORITY_ROLES:
        reason = (
            f"该资料属于 {_region_label(source_region)}官方来源，但当前项目面向"
            f"{_region_label(target_region)}，不会自动作为本地区服务流程依据。"
        )
        warning = "地区不匹配；可作为背景资料手动确认，但不替代本地区官方规则。"
    elif metadata.get("official_entry_evidence_type"):
        target = _metadata_str(candidate, "official_entry_target_url")
        reason = "该入口由品牌官方站点明确链接，可作为地区官方入口证据。"
        if target:
            reason += f"目标入口：{target}。"
        warning = (
            "该入口为公众号、小程序或其他不可直接抓取服务，需手动确认后再摄取。"
            if not auto_ingestible
            else ""
        )
    elif role == "repository" and technical_scope:
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
            "source_region": source_region,
            "target_region": target_region,
            "region_match": region_match,
            "brand_domain_candidate": brand_domain_candidate,
            "auto_ingestible": auto_ingestible,
            "selection_reason": reason,
            "manual_warning": warning,
        }
    )
    if isinstance(llm_assessment, dict):
        llm_reason = llm_assessment.get("selection_reason")
        if isinstance(llm_reason, str) and llm_reason.strip():
            metadata["hard_gate_reason"] = reason
            metadata["selection_reason"] = llm_reason.strip()
    return replace(candidate, metadata=metadata)


def _source_role(candidate: SourceCandidateDraft, *, brand_domain_candidate: bool = False) -> str:
    hinted = _metadata_str(candidate, "source_role")
    if hinted in ROLE_ORDER:
        return hinted
    combined = f"{candidate.title} {candidate.snippet}".lower()
    if _metadata_str(candidate, "official_entry_evidence_type"):
        return "first_party"
    if brand_domain_candidate:
        return "first_party"
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
    """Keep legal candidates; semantic quality is assessed by the bounded LLM layer."""
    role = _metadata_str(candidate, "source_role")
    if role not in PREFERRED_ROLES:
        return False
    if role in {"repository", "community_tool"} and scope_requires_direct_authority(scope):
        return False
    if candidate.metadata.get("auto_ingestible") is False:
        return False
    if candidate.metadata.get("region_match") == "cross_region":
        return False
    # A fixed URL/type score cannot decide whether a broad-domain public source
    # is relevant or useful. It remains a fallback ranking input, not a gate.
    return True


def _guided_rank_key(scope: str, candidate: SourceCandidateDraft) -> tuple[int, float, int, str]:
    role = _metadata_str(candidate, "source_role")
    direct_priority = 0 if scope_requires_direct_authority(scope) and role in DIRECT_AUTHORITY_ROLES else 1
    return (
        direct_priority,
        -candidate.authority_score,
        ROLE_ORDER.get(role, len(ROLE_ORDER)),
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


def infer_target_region(scope: str, *, language: str = "zh") -> str:
    """Infer a bounded regional target; Chinese-first defaults to mainland China."""
    normalized = scope.lower()
    for region in ("TW", "HK", "CN"):
        if any(marker in normalized for marker in REGION_LABELS[region]):
            return region
    return "CN" if language.lower().startswith("zh") else ""


def regional_official_query(scope: str, *, language: str = "zh") -> str:
    """Return one bounded regional query for an official-first evidence gap."""
    region = infer_target_region(scope, language=language)
    brand = _comparable_text(_brand_from_scope(scope))
    if not brand or not region:
        return ""
    labels = {"CN": "中国大陆", "TW": "台湾", "HK": "香港"}
    workflow_term = next((marker for marker in SERVICE_WORKFLOW_MARKERS if marker in scope.lower()), "服务流程")
    locale_hint = "简体中文" if region == "CN" else ""
    place_hint = "门店" if workflow_term in {"取号", "排队", "预约", "就餐"} else "服务"
    return (
        f"{brand} {labels.get(region, region)} 官方 {locale_hint} {place_hint} "
        f"微信公众号 小程序 {workflow_term}"
    ).strip()


def _official_evidence_gap(candidates: list[SourceCandidateDraft]) -> tuple[str, str]:
    if any(candidate.metadata.get("official_entry_evidence_type") for candidate in candidates):
        unavailable = any(
            candidate.metadata.get("official_entry_verification") == "unavailable"
            for candidate in candidates
        )
        reason = (
            "已找到品牌官方站点指向的本地区服务入口，但该入口暂时无法自动抓取或验证。"
            "已保留发现页、目标地址和地区信息；请先手动确认入口，或补充可访问的官方服务规则。"
        )
        return ("official_entry_unavailable" if unavailable else "official_entry_requires_confirmation", reason)
    if any(
        candidate.metadata.get("region_match") == "cross_region"
        and candidate.metadata.get("source_role") in DIRECT_AUTHORITY_ROLES
        for candidate in candidates
    ):
        return (
            "cross_region_official_only",
            "已找到其他地区的官方资料，但与当前项目地区不匹配，不能自动作为服务流程依据。"
            "请补充本地区官方帮助页、公告、服务规则或确认可用的地区入口。",
        )
    return (
        "evidence_insufficient",
        "该领域涉及品牌或机构服务流程，但未找到可验证的一方或直接权威资料。"
        "已保留第三方候选供手动确认；请补充官方帮助页、公告、服务规则或可访问的原始资料。",
    )


def _brand_identity_tokens(scope: str, candidates: list[SourceCandidateDraft]) -> set[str]:
    brand = _brand_from_scope(scope)
    if not brand:
        return set()
    tokens: set[str] = set()
    for candidate in candidates:
        title = _comparable_text(candidate.title)
        if brand not in title:
            continue
        if not any(marker in title for marker in OFFICIAL_PRESENTATION_MARKERS):
            continue
        tokens.update(_domain_identity_labels(candidate.url))
    return tokens


def _brand_from_scope(scope: str) -> str:
    normalized = scope.strip()
    if not normalized:
        return ""
    positions = [normalized.lower().find(marker) for marker in SERVICE_WORKFLOW_MARKERS]
    positions = [position for position in positions if position >= 0]
    brand = normalized[: min(positions)] if positions else normalized
    brand = re.sub(r"(?:在线|线下|门店|服务|流程|业务|系统)$", "", brand, flags=re.IGNORECASE)
    return brand.strip(" -_，,：:")


def _is_brand_domain_candidate(
    scope: str,
    candidate: SourceCandidateDraft,
    identity_tokens: set[str],
) -> bool:
    if candidate.metadata.get("brand_domain_candidate") is True:
        return True
    labels = _domain_identity_labels(candidate.url)
    if not labels or not identity_tokens.intersection(labels):
        return False
    brand = _comparable_text(_brand_from_scope(scope))
    title = _comparable_text(candidate.title)
    return bool(brand and (brand in title or any(token in title for token in identity_tokens)))


def _domain_identity_labels(url: str) -> set[str]:
    host = urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"com.cn", "com.tw", "com.hk", "co.jp"}:
        parts = parts[-3:]
    else:
        parts = parts[-2:]
    parts = [part for part in parts if part and part not in GENERIC_DOMAIN_LABELS]
    labels = {part for part in parts if len(part) >= 4 and part.replace("-", "").isalnum()}
    labels.update(
        token
        for part in parts
        for token in part.split("-")
        if len(token) >= 4 and token.isalnum() and token not in GENERIC_DOMAIN_LABELS
    )
    return labels


def _source_region(candidate: SourceCandidateDraft) -> str:
    explicit = _metadata_str(candidate, "source_region") or _metadata_str(candidate, "official_entry_region")
    if explicit:
        return explicit.upper()
    domain_region = _country_domain_region(candidate.url)
    if domain_region:
        return domain_region
    combined = f"{candidate.title} {candidate.snippet}".lower()
    for region, markers in REGION_LABELS.items():
        if any(marker in combined for marker in markers):
            return region
    return ""


def _country_domain_region(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    if host.endswith(".com.cn") or host.endswith(".cn"):
        return "CN"
    if host.endswith(".com.tw") or host.endswith(".tw"):
        return "TW"
    if host.endswith(".com.hk") or host.endswith(".hk"):
        return "HK"
    return ""


def _region_match(target_region: str, source_region: str) -> str:
    if not target_region or not source_region:
        return "unknown"
    return "match" if target_region == source_region else "cross_region"


def _region_label(region: str) -> str:
    return {"CN": "中国大陆", "TW": "台湾", "HK": "香港"}.get(region, "目标地区")


def _comparable_text(value: str) -> str:
    return value.lower().translate(TRADITIONAL_TO_SIMPLIFIED)
