from __future__ import annotations

from dataclasses import replace

from domain_atlas.demo.catalog import public_demo_catalog
from domain_atlas.evaluation.golden_demo import evaluate_catalog, load_manifest, render_markdown


def test_golden_demo_manifest_passes_for_the_curated_catalog():
    result = evaluate_catalog(public_demo_catalog(), generated_at="2026-07-18")

    assert result.manifest_version == "golden-demo-evaluation/v1"
    assert result.total == 25
    assert result.passed == 25
    assert result.passed_gate is True
    assert result.provider_calls == 0
    assert result.estimated_cost_usd == 0.0


def test_golden_demo_evaluation_detects_a_broken_source_catalog():
    catalog = public_demo_catalog()
    broken = replace(catalog, sources=catalog.sources[:3])

    result = evaluate_catalog(broken, generated_at="2026-07-18")
    failures = {case.case_id for case in result.cases if not case.passed}

    assert result.passed_gate is False
    assert "SRC-01" in failures


def test_golden_demo_report_is_machine_readable_and_explicit_about_limits():
    result = evaluate_catalog(public_demo_catalog(), manifest=load_manifest(), generated_at="2026-07-18")
    report = render_markdown(result)

    assert "Score: 25 / 25" in report
    assert "0 provider calls" in report
    assert "not generic model, retrieval, or RAG quality" in report
