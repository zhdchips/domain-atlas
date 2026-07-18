# GitHub Release Readiness Spec

## Purpose

Make Domain Atlas credible as a public engineering portfolio: a visitor can
understand its product boundary, run a deterministic local demo, verify the
core regression layers, and see how to deploy it safely without receiving an
unsafe invitation to expose a writable provider-backed instance.

## Product Positioning

Domain Atlas is a **traceable domain-learning system**. It turns selected
sources into an LLM Wiki, a structured learning path, and Wiki-first cited
question answering. Its workflows are controlled and evidence-oriented; it
must not be described as a fully autonomous general-purpose agent.

## Functional Requirements

### README And Public Narrative

- The README opens with the product category, a concise explanation, and real
  screenshots from the deterministic public Demo.
- It contains a readable architecture diagram for discovery, ingestion,
  Source/Chunk evidence, Wiki/graph/course generation, and cited QA.
- It documents Guided and Expert modes, citation/provenance boundaries, and
  clear failure behavior when a source is unavailable or insufficient.
- It gives copyable quick-start, configuration, deterministic test, Docker,
  and public-Demo instructions. Claims must match the current code and tests.

### Open Source Package

- Add MIT `LICENSE`, `.env.example`, a compact contribution guide,
  `CHANGELOG.md`, and `docs/release-notes/v0.1.0.md`.
- `.env.example` contains names and safe placeholders only. It must not include
  a usable secret or user-local path.
- The release notes identify v0.1.0 capabilities, verification, and known
  limitations without claiming a remote release has already happened.

### Container Delivery

- Add a production-oriented multi-stage `Dockerfile` and `.dockerignore`.
- The image installs runtime dependencies, runs as a non-root user, exposes
  port 8000, and allows `DATA_DIR` to be mounted for SQLite/Chroma/uploads.
- Document normal writable local usage separately from `PUBLIC_DEMO_MODE=true`.
- Never represent a public writable deployment as safe by default; document
  remaining SSRF, billing, rate-limit, authentication, and tenant-isolation
  work.

### Continuous Integration

- Add a GitHub Actions workflow for pull requests and pushes.
- A deterministic job runs `--fast`, `--e2e`, and `--golden-demo-eval` without
  provider credentials.
- A separate browser job installs Chromium and runs `--browser-e2e`.
- Cache uv dependencies, use a supported Python version, and upload useful
  reports only when a job fails. No live provider regression runs in CI.

### Release Audit

- Audit tracked content for secrets, local paths, data artifacts, and generated
  files. Update ignores for Docker contexts, screenshots, and reports as
  required.
- Record remote publication steps (default branch, push, tag/release, hosted
  Demo URL) as a checklist. Do not change remote state.

## Acceptance Criteria

1. A newcomer can start the deterministic public Demo or normal local app from
   the README and understand required configuration.
2. The README contains verified screenshots and an accurate architecture
   overview; it distinguishes evidence-backed workflows from autonomous claims.
3. `docker build` succeeds and the public-Demo container responds on port 8000
   as a non-root process.
4. The GitHub workflow is valid and runs only deterministic checks without
   secrets.
5. `--fast`, `--e2e`, `--golden-demo-eval`, and `--browser-e2e` pass locally.
6. The repository audit contains no tracked secrets or user-local paths, and
   release documentation records remaining deployment risks and remote steps.
