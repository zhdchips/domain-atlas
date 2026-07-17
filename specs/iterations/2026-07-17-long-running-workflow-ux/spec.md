# Long-running Workflow UX

## Problem

Search, source ingestion, knowledge building, autopilot, and QA can take visible time, but the current form posts provide no immediate feedback and expose provider failures as raw JSON.

## Scope

- Give all submitted forms a reusable pending state that disables duplicate submission and announces a Chinese action-specific status.
- Run autopilot, knowledge build, and individual ingestion in a local background thread. Persist queued, running, completed, failed, and interrupted workflow state in SQLite.
- Show a polling "当前任务" area on the dashboard with readable progress, completed steps, and errors.
- Reject conflicting project-wide long-running work. Preserve ordinary HTML form submission when JavaScript is unavailable.
- Render form failures in-page after redirect rather than as JSON.

## Non-goals

- Distributed workers, a broker, authentication, cancellation, or making QA asynchronous.
- A new frontend framework or a replacement for the existing Jinja pages.

## Acceptance criteria

1. Background endpoints respond with a redirect without waiting for LLM or network completion.
2. Dashboard polling exposes task state and Chinese step labels after refresh.
3. A second build/autopilot/ingestion request while another long task is active cannot create a second run.
4. Forms show pending copy, disabled controls, and accessible busy state before navigation.
5. Failed actions show contextual Chinese errors on the relevant page.
6. Deterministic, browser, and live E2E layers cover the changed path.
