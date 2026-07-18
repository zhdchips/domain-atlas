# GitHub Release Readiness Tasks

## Phase 1: Specification

- [x] Audit current documentation, ignores, package entry points, remote state, and release risks.
- [x] Define public positioning, deterministic verification, container, CI, and remote-boundary requirements.
- [x] Commit specification phase.

## Phase 2: Release Artifacts

- [x] Capture deterministic public-Demo screenshots.
- [x] Rewrite README and add open-source/release documents.
- [x] Add Docker delivery and GitHub Actions CI.
- [x] Commit implementation phase.

## Phase 3: Verification And Audit

- [x] Validate documentation links/workflow syntax and audit tracked files.
- [x] Attempt to build and run the public-Demo Docker image; record the local daemon blocker if unavailable.
- [x] Run deterministic regression layers and confirm the local service remains healthy.
- [x] Commit verification phase.

## Verification Notes

- README local links, screenshot references, and GitHub Actions YAML parse successfully.
- The release audit found no tracked secrets, user-local paths, or image metadata
  containing secrets. A historical live intake report was removed from Git while
  retained locally under an ignored path.
- `docker build -t domain-atlas:release-check .` could not begin because the
  local OrbStack Docker socket is unavailable. The Dockerfile has not produced a
  daemon-side build error; container runtime verification remains an
  environment-dependent follow-up.
- `uv run python scripts/regression.py --fast`: passed, 136 pytest cases and
  the 13-case offline intake evaluation.
- `uv run python scripts/regression.py --e2e`: passed, 3 deterministic E2E cases.
- `uv run python scripts/regression.py --golden-demo-eval`: passed, 25/25.
- `uv run python scripts/regression.py --browser-e2e`: passed, including both
  the deterministic project UI and the read-only public Demo.
