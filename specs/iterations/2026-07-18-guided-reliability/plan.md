# Guided Autopilot Reliability Plan

## Architecture

The workflow remains a single persisted SQLite-backed background task. Discovery returns drafts, the workflow turns them into a stable candidate queue, and each queue entry is attempted at most once. The queue is consumed until two source ingestions succeed; those source IDs are passed to the existing build workflow through the project repository.

The workflow will write structured attempt details to the existing `workflow_steps.output_json`; a schema migration is unnecessary for this iteration. The dashboard derives readable summaries from that structured output rather than parsing error strings from the run row.

`URLLoader` errors will carry enough stable context for classification without exposing request headers or secrets. The workflow owns translation from technical ingestion errors to learner-facing recovery guidance.

## Implementation Steps

1. Add a recorded candidate/URL fixture and fake providers that exercise actual discovery, ingestion, build, embedding, and QA contracts without external calls.
2. Refactor candidate ordering into an explicit queue helper that preserves deduplication, authority-first ranking, and domain caps while retaining fallback candidates beyond the two-source gate.
3. Refactor `AutopilotWorkflow.run` to consume the queue until the gate is reached or exhausted; persist structured attempts and terminal reason.
4. Add failure classification and dashboard presentation helpers.
5. Update workflow status/template copy, guided helper copy, and step labels.
6. Add deterministic workflow, app E2E, and browser flow coverage.
7. Add isolated `live-guided-e2e` using a temporary data directory and an environment-controlled query, then expose it from `scripts/regression.py`.
8. Run deterministic, browser, live fixed-build, and live guided checks; document actual results in `tasks.md`.

## Design Decisions

- The gate is two successful sources, not five. It prioritizes finishing with minimally diverse evidence over spending time on lower-ranked sources after enough usable evidence exists.
- Candidate attempt details live in JSON workflow outputs because they are run-scoped audit data, not long-lived source metadata.
- `access_denied` receives recovery guidance to use another source; `network` and `timeout` receive retry guidance; `parse` and `embedding` point to manual files or configuration checks.
- The browser layer uses deterministic injected providers and a server fixture. It validates the same DOM a learner sees while avoiding provider costs.

## Risks And Mitigations

- A live search may return fewer than two ingestible sources. The live script reports this as a meaningful terminal outcome with the attempt summary, rather than treating the check as a false success.
- A single page can be very large or slow. Existing 180-second build timeout and retry configuration remains the guardrail; the live script has an overall timeout.
- Search ranking may shift. Recorded fixtures validate queue policy; live checks validate external compatibility without asserting a vendor-specific list.
