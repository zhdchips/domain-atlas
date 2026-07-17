# Plan

1. Extend workflow persistence with queued/running transitions, active-run lookup, and startup interruption handling.
2. Add a minimal thread-backed task runner and reuse existing workflow classes by allowing a caller-provided run id.
3. Emit progress at meaningful ingestion, build, and autopilot boundaries.
4. Add dashboard status partial polling, form pending enhancement, responsive styles, and redirect-based error messages.
5. Extend application and Playwright checks, then run fast, browser, and live E2E regression layers.

## Task model

The web request creates one persisted queued run under a process-local lock and starts a daemon thread. The thread marks it running, writes steps, and finishes or fails it. No in-memory state is the source of truth; the thread registry only prevents a local race. On app startup, queued/running rows are marked `interrupted` with a retryable explanation.

## Conflict policy

One long-running task is allowed per project. This is intentionally stricter than only excluding build/autopilot: it prevents a build from racing an ingestion and prevents duplicate source ingestion. Lightweight forms remain available, while the UI explains why long-task buttons are disabled.
