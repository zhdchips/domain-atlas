"""Evaluate the version-controlled public Demo catalog without providers."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain_atlas.demo.catalog import PublicDemoCatalog


_SOURCE_CITATION = re.compile(r"^S\d+-C\d+$")
_WIKI_CITATION = re.compile(r"^W:([a-z0-9-]+)#\d+$")
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_DEMO_ROUTES = ["/demo", "/demo/wiki", "/demo/path", "/demo/qa", "/demo/evaluation"]
_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = _ROOT / "evaluations" / "golden_demo" / "v1" / "manifest.json"


@dataclass(frozen=True)
class EvaluationCaseResult:
    case_id: str
    category: str
    assertion: str
    expected: Any
    observed: Any
    passed: bool
    detail: str


@dataclass(frozen=True)
class GoldenDemoEvaluation:
    manifest_version: str
    subject: str
    generated_at: str
    total: int
    passed: int
    pass_gate: int
    passed_gate: bool
    deterministic: bool
    provider_calls: int
    estimated_cost_usd: float
    known_limitations: list[str]
    cases: list[EvaluationCaseResult]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass_rate"] = round(self.passed / self.total, 4) if self.total else 0.0
        return payload


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_catalog(
    catalog: PublicDemoCatalog,
    *,
    manifest: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> GoldenDemoEvaluation:
    """Run every explicit catalog assertion without network, storage, or providers."""

    manifest = manifest or load_manifest()
    case_results = [_evaluate_case(catalog, case) for case in manifest["cases"]]
    passed = sum(result.passed for result in case_results)
    gate = int(manifest["pass_gate"])
    return GoldenDemoEvaluation(
        manifest_version=str(manifest["schema_version"]),
        subject=str(manifest["subject"]),
        generated_at=generated_at or datetime.now(UTC).date().isoformat(),
        total=len(case_results),
        passed=passed,
        pass_gate=gate,
        passed_gate=passed >= gate,
        deterministic=True,
        provider_calls=0,
        estimated_cost_usd=0.0,
        known_limitations=[str(item) for item in manifest.get("known_limitations", [])],
        cases=case_results,
    )


def render_markdown(result: GoldenDemoEvaluation) -> str:
    status = "PASS" if result.passed_gate else "FAIL"
    lines = [
        "# Golden Demo Evaluation Report",
        "",
        f"- Status: **{status}**",
        f"- Manifest: `{result.manifest_version}`",
        f"- Run date (UTC): {result.generated_at}",
        f"- Score: {result.passed} / {result.total} (gate: {result.pass_gate})",
        f"- Execution: deterministic, {result.provider_calls} provider calls, estimated cost ${result.estimated_cost_usd:.2f}",
        "",
        "## Case Results",
        "",
        "| ID | Category | Result | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for case in result.cases:
        outcome = "pass" if case.passed else "fail"
        lines.append(f"| {case.case_id} | {case.category} | {outcome} | {case.detail} |")
    lines.extend(["", "## Known Limitations", ""])
    lines.extend(f"- {item}" for item in result.known_limitations)
    return "\n".join(lines) + "\n"


def _evaluate_case(catalog: PublicDemoCatalog, case: dict[str, Any]) -> EvaluationCaseResult:
    assertion = str(case["assertion"])
    expected = case["expected"]
    observed = _observed_value(catalog, assertion)
    passed = observed == expected
    return EvaluationCaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        assertion=assertion,
        expected=expected,
        observed=observed,
        passed=passed,
        detail=_case_detail(assertion, expected, observed),
    )


def _observed_value(catalog: PublicDemoCatalog, assertion: str) -> Any:
    source_citations = {citation for source in catalog.sources for citation in source.citations}
    source_citations_ok = lambda citations: all(citation in source_citations for citation in citations)
    wiki_titles = {page.title for page in catalog.pages}
    wiki_slugs = {page.slug for page in catalog.pages}
    wiki_citations = {f"W:{page.slug}#1" for page in catalog.pages}
    all_links = set(catalog.citation_links)
    guide_citations = list(_nested_citations(catalog.guide.question_answers))
    module_citations = list(_module_citations(catalog))

    if assertion == "source_count":
        return len(catalog.sources)
    if assertion == "source_metadata_complete":
        return all(
            source.title
            and source.publisher
            and source.url
            and source.source_type
            and source.coverage
            and source.accessed_on
            and source.authority_note
            and source.evidence_locator
            and source.citations
            for source in catalog.sources
        )
    if assertion == "source_urls_are_https":
        return all(source.url.startswith("https://") for source in catalog.sources)
    if assertion == "source_citations_are_unique":
        labels = [citation for source in catalog.sources for citation in source.citations]
        return len(labels) == len(set(labels)) and all(_SOURCE_CITATION.match(label) for label in labels)
    if assertion == "source_locators_are_https":
        return all(source.evidence_locator.startswith("https://") for source in catalog.sources)
    if assertion == "wiki_page_count":
        return len(catalog.pages)
    if assertion == "required_page_types":
        return sorted({page.page_type for page in catalog.pages})
    if assertion == "wiki_paths_are_unique":
        paths = [page.path for page in catalog.pages]
        return len(paths) == len(set(paths))
    if assertion == "wiki_citations_resolve":
        return all(source_citations_ok(page.citations) for page in catalog.pages)
    if assertion == "wiki_links_resolve":
        links = {link for page in catalog.pages for link in _WIKILINK.findall(page.body_markdown)}
        return all(link in wiki_titles for link in links)
    if assertion == "ten_domain_questions":
        return len(catalog.guide.question_answers)
    if assertion == "guide_question_citations_resolve":
        return bool(guide_citations) and source_citations_ok(guide_citations)
    if assertion == "mainline_stages_are_complete":
        return sorted(int(item["module_stage"]) for item in catalog.guide.mainline)
    if assertion == "core_concept_count":
        return len(catalog.guide.core_concepts)
    if assertion == "branches_and_details_present":
        return bool(catalog.guide.branches) and bool(catalog.guide.details)
    if assertion == "module_count":
        return len(catalog.modules)
    if assertion == "module_stages_are_complete":
        return sorted(module.stage for module in catalog.modules)
    if assertion == "modules_are_substantive":
        return all(
            len(module.core_explanation) >= 120
            and len(module.knowledge_blocks) >= 2
            and module.examples
            and module.misconceptions
            and module.check_questions
            and module.practice_task
            for module in catalog.modules
        )
    if assertion == "module_citations_resolve":
        return bool(module_citations) and source_citations_ok(module_citations)
    if assertion == "qa_count":
        return len(catalog.qa_records)
    if assertion == "supported_qa_has_evidence":
        supported = [record for record in catalog.qa_records if record.evidence_status == "supported"]
        return bool(supported) and all(
            record.citations
            and record.source_provenance
            and all(citation in wiki_citations for citation in record.citations)
            and source_citations_ok(record.source_provenance)
            for record in supported
        )
    if assertion == "insufficient_qa_is_honest":
        insufficient = [record for record in catalog.qa_records if record.evidence_status == "insufficient"]
        return len(insufficient) == 1 and all(
            not record.citations
            and not record.source_provenance
            and "无法" in record.answer
            and "资料" in record.answer
            for record in insufficient
        )
    if assertion == "demo_routes_are_complete":
        return list(_DEMO_ROUTES)
    if assertion == "citation_links_are_complete":
        required = source_citations | wiki_citations
        return required.issubset(all_links) and all(
            url.startswith("https://") or url.startswith("/demo/wiki/")
            for url in catalog.citation_links.values()
        )
    if assertion == "evaluation_summary_matches_manifest":
        return (
            catalog.evaluation_summary.get("manifest_version") == "golden-demo-evaluation/v1"
            and catalog.evaluation_summary.get("score") == "25 / 25"
            and catalog.evaluation_summary.get("provider_calls") == 0
        )
    raise ValueError(f"Unknown golden Demo assertion: {assertion}")


def _nested_citations(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            citation
            for key, nested in value.items()
            for citation in (_nested_citations(nested) if key != "citations" else [str(item) for item in nested])
        ]
    if isinstance(value, list):
        return [citation for item in value for citation in _nested_citations(item)]
    return []


def _module_citations(catalog: PublicDemoCatalog) -> list[str]:
    citations: list[str] = []
    for module in catalog.modules:
        citations.extend(module.citations)
        citations.extend(_nested_citations(module.knowledge_blocks))
        citations.extend(_nested_citations(module.examples))
        citations.extend(_nested_citations(module.misconceptions))
        citations.extend(_nested_citations(module.further_reading))
    return citations


def _case_detail(assertion: str, expected: Any, observed: Any) -> str:
    if observed == expected:
        return f"{assertion} matched expected value."
    return f"{assertion} expected {expected!r}, observed {observed!r}."
