"""Run Domain Atlas regression layers."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run layered Domain Atlas regression checks.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fast", action="store_true", help="Run the default deterministic test suite.")
    group.add_argument("--e2e", action="store_true", help="Run deterministic end-to-end tests.")
    group.add_argument("--live", action="store_true", help="Run live provider smoke checks.")
    group.add_argument(
        "--intake-eval",
        action="store_true",
        help="Run the deterministic versioned intake evaluation case set.",
    )
    group.add_argument(
        "--live-intake-eval",
        action="store_true",
        help="Run the opt-in live LLM intake evaluation case set.",
    )
    group.add_argument(
        "--live-e2e",
        action="store_true",
        help="Run a fixed live E2E domain build with configured providers.",
    )
    group.add_argument(
        "--live-guided-e2e",
        action="store_true",
        help="Run an isolated live guided search, ingestion, build, and QA flow.",
    )
    group.add_argument(
        "--browser-e2e",
        action="store_true",
        help="Run Playwright browser layout checks against a deterministic Wiki project.",
    )
    args = parser.parse_args()

    if args.fast:
        return _run_many(
            "fast",
            [[sys.executable, "-m", "pytest"], [sys.executable, "scripts/intake_eval.py", "--offline"]],
        )
    if args.e2e:
        return _run("e2e", [sys.executable, "-m", "pytest", "tests/e2e"])
    if args.live:
        return _run("live", [sys.executable, "scripts/smoke_providers.py"])
    if args.intake_eval:
        return _run("intake-eval", [sys.executable, "scripts/intake_eval.py", "--offline"])
    if args.live_intake_eval:
        return _run("live-intake-eval", [sys.executable, "scripts/intake_eval.py", "--live"])
    if args.live_e2e:
        return _run("live-e2e", [sys.executable, "scripts/live_e2e_domain_build.py"])
    if args.live_guided_e2e:
        return _run("live-guided-e2e", [sys.executable, "scripts/live_guided_e2e.py"])
    return _run_many(
        "browser-e2e",
        [
            [sys.executable, "scripts/browser_e2e_wiki_layout.py"],
            [sys.executable, "scripts/browser_e2e_public_demo.py"],
        ],
    )


def _run(layer: str, command: list[str]) -> int:
    print(f"Running {layer} regression: {' '.join(command)}", flush=True)
    return subprocess.run(command).returncode


def _run_many(layer: str, commands: list[list[str]]) -> int:
    for command in commands:
        if _run(layer, command) != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
