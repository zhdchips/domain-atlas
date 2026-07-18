# Guided Autopilot Reliability Spec

## Purpose

Make guided mode dependable when it encounters the ordinary instability of public-web learning sources: variable search results, anti-bot `403` responses, extraction failures, embedding failures, and slow LLM builds. The system should use the best evidence it can obtain, communicate what happened, and leave the learner with a clear recovery path.

## User Problem

The current guided workflow ranks candidates and attempts a small selected set. If every selected page rejects the URL loader, the run ends with `All selected sources failed ingestion.` This loses the useful lower-ranked candidates already returned by search and gives the learner too little context to recover.

The current regression suite validates deterministic workflow contracts, a fixed Markdown-to-Wiki live build, and browser layout. It does not replay realistic search plus mixed URL outcomes, nor does browser automation exercise the interactive guided workflow state.

## Functional Requirements

### Candidate Queue And Build Gate

- Treat discovered candidates as an ordered, deduplicated queue rather than a fixed batch.
- Preserve authority-first ranking, fallback eligibility, and the existing per-domain cap of two candidates.
- Attempt candidates in queue order until either:
  - `MIN_BUILD_SOURCES = 2` sources have been ingested successfully; or
  - the queue is exhausted.
- Two sources are the MVP build gate because a single source can produce a technically valid Wiki but cannot provide even minimal cross-source coverage or resilience to a narrow/partial page. A learner may still manually build from one source outside guided mode.
- Do not retry a candidate that has already failed within the same run.
- Once the build gate is reached, do not continue consuming lower-ranked candidates in that run.
- If at least two sources succeed, build the knowledge base even when earlier candidates failed.

### Failure Classification And Recovery

- Persist an `attempted_sources` list in the final ingestion step. Each item includes candidate/source identifiers, title, URL, outcome, error category, detail, and whether a retry may help.
- Classify failures as `access_denied`, `network`, `timeout`, `parse`, `embedding`, or `unknown` using the source error and exception chain where available.
- The terminal reason is one of `minimum_sources_reached` or `candidates_exhausted`.
- When candidates are exhausted before the build gate, use a learner-facing error that states the number of successful sources, common failure categories, and a recovery action: retry later, manually add an accessible URL/Markdown/PDF, or adjust the domain scope.
- Keep raw technical details in the persisted workflow steps but render a concise Chinese summary on the dashboard.
- A transient provider/build failure must retain its existing detailed provider error and remain separately distinguishable from source exhaustion.

### Guided Mode UI

- The dashboard's guided-mode helper copy explains that the workflow aims to obtain two usable sources before constructing the Wiki.
- The workflow panel shows final source success count and failed-source summary after a run.
- Exhaustion errors include an explicit recovery action and do not expose only the previous generic English message.
- Existing pending form state, background execution, and polling behavior remain intact.

## Regression Requirements

### Deterministic Tests

- Add unit/workflow coverage for: strict candidates failing with fallback success, partial failures, all candidates exhausted, duplicate candidates, and per-domain cap.
- Add error classification coverage for `403`, timeout/network, parsing, and embedding failures.
- Add a recorded guided fixture containing normalized Exa-style candidate drafts plus deterministic URL responses for successful pages and blocked pages. It must run without network, LLM, or embedding cost.
- Add a deterministic app E2E that uses the recorded fixture through real guided routes and verifies successful build after blocked candidates.

### Browser E2E

- Extend the Playwright check with deterministic server fixtures that exercise: create project, clarification confirmation, submit guided build, observe active workflow UI, and inspect terminal success and exhaustion summaries.
- Browser checks remain offline and must not call external providers.

### Live Checks

- Keep `--live-e2e` as the fixed Markdown build/QA verification.
- Add opt-in `--live-guided-e2e`. It performs one real search, attempts real URL ingestion, then builds and asks a cited question if the two-source gate is reached. It reports candidate count, attempted/successful source count, elapsed time, and terminal outcome without leaking secrets.
- The live guided check is only required once at the end of a reliability SDD iteration. It must not alter the user's normal project data.

## Non-Goals

- No distributed workers, browser-based scraping, CAPTCHA bypass, or promise that every public website is ingestible.
- No automatic project reset or deletion of sources. A future explicit “reset and rebuild” capability should use the final ingestion attempts and source provenance introduced here.
- No LangGraph or replacement of the current SQLite, FastAPI, Jinja, or provider-adapter architecture.
- No live calls in default test commands.

## Acceptance Criteria

1. A `旅行代理`-shaped recorded search result with blocked encyclopedia pages continues to accessible fallback sources and produces a Wiki, learning route, and cited QA answer after two successful ingestions.
2. Queue exhaustion stops cleanly with persisted attempt details and a Chinese recovery summary.
3. Guided mode does not ingest more candidates after it has reached two successful sources.
4. `uv run python scripts/regression.py --fast`, `--e2e`, and `--browser-e2e` pass without network or LLM use.
5. `uv run python scripts/regression.py --live-e2e` and `--live-guided-e2e` run successfully once against configured providers, or report a precise external failure with their isolated temporary work directories preserved.
6. The iteration does not modify `.env`, delete existing project data, or push commits.

## Regression Maintenance

- Add a recorded fixture whenever a real candidate shape or source failure reveals a new workflow decision.
- Keep recorded assertions focused on behavior and stable categories, not vendor-specific response wording.
- Run `--fast` and `--browser-e2e` after every iteration touching guided workflow/UI; run `--live-guided-e2e` after changes to discovery, ingestion, build, provider timeouts, or candidate ranking.
