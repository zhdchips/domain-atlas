"""Run deterministic or live quality evaluation for LLM-led project intake."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from domain_atlas.core.settings import Settings
from domain_atlas.intake.evaluation import (
    IntakeEvaluationError,
    RecordedIntakeAssessmentProvider,
    evaluate_case_set,
    load_case_set,
    render_report,
    write_report,
)
from domain_atlas.intake.suggestions import LLMIntakeAssessmentProvider
from domain_atlas.providers.chat import OpenAICompatibleChatProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_SET = PROJECT_ROOT / "evals" / "intake" / "cases.v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Domain Atlas intake assessment quality.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Replay recorded assessments without a network call.")
    mode.add_argument("--live", action="store_true", help="Call the configured LLM once for every case.")
    parser.add_argument("--case-set", type=Path, default=DEFAULT_CASE_SET, help="Versioned case-set JSON path.")
    parser.add_argument("--report", type=Path, help="Optional output path for the normalized JSON report.")
    args = parser.parse_args()

    try:
        case_set = load_case_set(args.case_set)
    except IntakeEvaluationError as exc:
        print(f"FAIL intake-eval: {exc}")
        return 2

    mode_name = "live" if args.live else "offline"
    if args.live:
        settings = Settings()
        if not _live_provider_configured(settings):
            print("FAIL live intake-eval: configured LLM credentials are missing.")
            return 2
        provider = LLMIntakeAssessmentProvider(
            OpenAICompatibleChatProvider(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.chat_model,
                max_tokens=900,
                timeout_seconds=settings.intake_llm_timeout_seconds,
                max_retries=0,
                json_retries=0,
            )
        )
    else:
        provider = RecordedIntakeAssessmentProvider(case_set.cases)

    report = evaluate_case_set(
        case_set,
        provider,
        mode=mode_name,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    report_path = args.report or (_default_live_report_path(case_set.name) if args.live else None)
    if report_path is not None:
        write_report(report, report_path)
        print(f"report={report_path}")
    print(render_report(report))
    return 0 if report.gate_passed else 1


def _live_provider_configured(settings: Settings) -> bool:
    return bool(settings.llm_api_key.strip() and settings.llm_base_url.strip() and settings.chat_model.strip())


def _default_live_report_path(case_set: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "reports" / "intake" / f"{case_set}-{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
