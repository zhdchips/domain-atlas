# Golden Demo and Evaluation Spec

## Purpose

Turn the public read-only Demo into a credible portfolio artifact: a curated,
source-grounded learning case with a versioned evaluation that can be rerun
without providers.

## Scope

- Keep `Agent Harness Engineering` as the single golden Demo domain.
- Curate four publicly accessible first-party sources: OpenAI Agents SDK,
  LangGraph documentation, and two Anthropic engineering articles.
- Record per-source publisher, type, URL, access date, authority rationale,
  coverage, and a stable locator for the cited claim.
- Enrich the catalog with a ten-question domain overview, concept dependencies,
  seven Wiki pages across index/log/source/concept/synthesis types, five
  substantive learning modules, and five cited QA examples.
- Include one evidence-insufficient QA example that explicitly declines to
  invent a universal answer and carries no fabricated citation.
- Make public Demo citations directly clickable to either their source locator
  or the matching Demo Wiki page.
- Expose a public evaluation summary that clearly labels the result as a
  deterministic golden-catalog integrity check, not a model benchmark or a
  production accuracy claim.

## Evaluation Contract

- Store the versioned 25-case manifest, scoring rubric, manual review record,
  and committed baseline report under `evaluations/golden_demo/v1/`.
- The deterministic evaluator reads only the in-memory catalog and manifest.
  It must make no network request, database connection, or provider call.
- Cases cover source authority/provenance, Wiki structure and citations,
  learning-guide coverage, learning-module depth, supported QA, evidence
  insufficiency, and Demo navigation metadata.
- Every case is an explainable assertion. The baseline gate is `25 / 25`.
- The evaluator can write a JSON result and Markdown report. Generated reports
  state manifest version, UTC run date, outcome, known limitations, and zero
  provider cost for the deterministic run.
- The manual review rubric remains a separate, explicit qualitative check; an
  LLM judge is not used as a release gate.

## Boundaries

- `PUBLIC_DEMO_MODE=true` remains an in-memory, zero-provider, zero-write
  surface. The golden catalog cannot read normal `data/` projects.
- This iteration does not claim that a fixed catalog measures generic RAG,
  retrieval, or model quality. It verifies that this selected demonstration has
  complete structure and traceable evidence.
- A live provider E2E may be run once as a separate, opt-in build smoke check.
  It is not part of the golden catalog score and must use an isolated temporary
  data directory.
- Do not add authentication, public writes, cloud infrastructure, or user API
  key flows.

## Acceptance Criteria

- `/demo` exposes the source catalog, Wiki, learning route, cited QA, and
  evaluation result without a form or provider invocation.
- All source citations resolve to catalog entries with absolute HTTPS URLs and
  all Wiki citations resolve to Demo Wiki routes.
- The evaluator passes the complete 25-case manifest, produces machine-readable
  and Markdown results, and fails when a required catalog invariant is broken.
- Deterministic app, evaluator, E2E, and Playwright checks prove the golden
  content and preserve the public safety boundary and local-first behavior.
- README explains the Demo route, suggested walkthrough, source scope,
  evaluation result, and its non-generalization limitation.
