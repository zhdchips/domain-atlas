# Provider Resilience Spec

## Purpose

Make Domain Atlas's external-provider boundaries consistently recover from ordinary, transient failures while preserving trustworthy workflow history and safe learner-facing recovery guidance.

## Problem

Exa and chat currently contain separate retry loops. Embedding and URL fetching fail on the first transport error. Retry eligibility, backoff, timeout configuration, failure details, and workflow visibility are consequently inconsistent. Some provider error paths also expose unbounded upstream response text.

## Scope

Apply one shared HTTP resilience policy to the read/request boundaries used by:

- Exa candidate search;
- OpenAI-compatible chat completion;
- OpenAI-compatible embedding generation;
- URL fetching during source ingestion.

The iteration does not add a queue service, circuit breaker, distributed tracing, or automatic retry of complete workflows.

## Functional Requirements

### Shared Policy

- A provider request has an explicit timeout, maximum retry count, exponential base delay, and bounded random jitter, all configurable through `Settings` / `.env`.
- Defaults allow at most three total attempts.
- Retry only transport errors, timeouts, HTTP `429`, and HTTP `500`, `502`, `503`, or `504`.
- Do not retry `401`, `403`, other client errors, malformed responses, parsing failures, or invalid LLM JSON.
- Retries emit safe structured events containing provider, operation, attempt/maximum, category, retryability, and learner recovery advice. Events must never contain credentials, request content, or upstream response bodies.

### Provider Behavior

- Exa, chat, embeddings, and URL loading all delegate transport retry decisions to the shared module.
- Provider-specific public interfaces and exception types remain stable where possible; their errors use safe summaries rather than raw upstream payloads.
- LLM JSON parse/format failures are terminal for an individual completion request. Knowledge-build structural repair remains a separate workflow-level operation.

### Workflow Visibility

- Long-running routes attach a workflow retry observer to their providers.
- The workflow status panel distinguishes a retry in progress, a recovered request, and a terminal provider failure.
- Terminal failures retain an actionable category and recovery message in persisted workflow step output, while the run error remains concise and secret-safe.

### Idempotency Boundary

- Only read/request operations are retried by this layer.
- No workflow run, source, chunk, artifact, or vector write is retried by the resilience layer.
- Existing unique source locator and replace-by-source/rebuild persistence semantics must continue preventing duplicate Domain Atlas records when a user manually retries a task.

## Configuration

| Setting | Default | Applies to |
| --- | --- | --- |
| `SEARCH_TIMEOUT_SECONDS` | `30` | Exa search |
| `LLM_TIMEOUT_SECONDS` | `180` | Chat completion |
| `EMBEDDING_TIMEOUT_SECONDS` | `45` | Embedding |
| `URL_FETCH_TIMEOUT_SECONDS` | `30` | URL ingestion |
| `SEARCH_MAX_RETRIES` | `2` | Exa search |
| `LLM_MAX_RETRIES` | `2` | Chat completion |
| `EMBEDDING_MAX_RETRIES` | `2` | Embedding |
| `URL_FETCH_MAX_RETRIES` | `2` | URL ingestion |
| `PROVIDER_RETRY_BASE_DELAY_SECONDS` | `1` | all providers |
| `PROVIDER_RETRY_JITTER_SECONDS` | `0.2` | all providers |

`MAX_RETRIES=2` means one initial request plus at most two retries.

## Acceptance Criteria

- Deterministic tests prove retry-success, retry-exhaustion, non-retryable failure, retryable HTTP statuses, and safe error output for all four boundaries.
- Tests prove URL retry does not duplicate source/chunk records and that manual re-ingestion retains existing idempotent replacement behavior.
- Workflow tests and browser E2E prove the retry/recovered/terminal summaries are visible without external network calls.
- `--fast`, `--e2e`, and `--browser-e2e` pass. One opt-in live provider check is run after implementation and its API-cost implications are reported.
