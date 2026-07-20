# LLM-Assisted Source Selection Spec

## Purpose

Make guided discovery useful for broad learning domains without weakening the
evidence rules required for concrete branded service workflows. The system must
separate deterministic safety/evidence gates from semantic source assessment.

## User Problem

The current candidate policy assigns most public web pages the same low score
from URL/type heuristics. `短视频自媒体入门与运营` can therefore discover twelve
relevant-looking sources yet fail before any semantic assessment. Conversely,
`旅行代理` can exhaust a two-item queue when one encyclopedia returns 403.

The product needs a small, bounded model judgement for relevance, authority,
coverage, and source risk. It must remain safe when that judgement is absent or
invalid, and it must not let a model bypass direct-evidence requirements.

## Functional Requirements

### Two-Layer Selection

1. A deterministic hard gate removes unsafe, duplicate-family, cross-region,
   and explicitly non-ingestible candidates. It keeps the existing direct
   first-party/primary-document requirement for branded service workflows.
2. A single LLM candidate-assessment call evaluates the remaining candidate
   batch. It returns one assessment per candidate with `relevance`,
   `authority`, `coverage_topics`, `risk_flags`, `priority`, and
   `selection_reason`; it also returns `missing_coverage` and up to three
   supplemental search queries.
3. The assessment payload is bounded and strictly validated. Candidate IDs must
   be known, exactly one valid assessment is accepted per candidate, scores are
   finite values in `[0, 1]`, priority is bounded, text fields are length
   limited, and queries are deduplicated, short, and free of URLs/instructions.
4. The model cannot add candidates, alter regions, mark a source as direct
   authority, or relax the service-workflow gate.

### Queue, Fallback, And Search Budget

1. Guided ingestion receives an ordered queue of up to six candidates and
   attempts each once until two successfully ingested independent families are
   available.
2. A 403, timeout, parse failure, or embedding failure records an attempt and
   advances to the next queue candidate. No candidate is retried by the queue.
3. When the first search cannot form a viable queue for a normal learning
   domain, execute at most one supplemental search round using validated LLM
   query suggestions. The same hard gate and assessment process then runs over
   the merged discovery set.
4. When model assessment is unconfigured, fails, is invalid, or is below the
   configured confidence threshold, use a deterministic fallback ranking. That
   fallback may offer broad-domain public-web candidates, but it must preserve
   all hard gates and record why LLM assessment was not applied.
5. A branded service workflow with no direct evidence fails before ingestion.
   Supplemental third-party sources and model rankings cannot override that
   result.

### Explainability

- Persist selection mode, assessment source/status, candidate assessment
  summaries, whether a supplemental search was used, and its bounded query
  count in workflow step output.
- Explain four distinct terminal conditions in learner-facing Chinese:
  low-quality/marketing-heavy discovery, missing direct authority, inaccessible
  sources, and evidence exhaustion after supplemental search.
- Manual source confirmation remains available and retains source role and
  warnings in provenance.

## Non-Goals

- No LangGraph, browser automation, CAPTCHA bypass, domain allowlists, or
  case-specific rules.
- No changes to public Demo data, existing project data, or deployment config.
- No provider calls in default tests.

## Acceptance Criteria

1. A recorded `短视频自媒体入门与运营` candidate set with only low-scored web
   sources receives either a model-ranked queue or one bounded supplemental
   search; it never fails solely because every source has the old `0.43` score.
   If evidence remains inadequate, its recovery text identifies marketing/
   experience-heavy material rather than asking for a service rule.
2. A recorded `旅行代理` set advances beyond a blocked encyclopedia candidate
   into later eligible candidates and completes after two independent ingests.
3. `寿司郎取号流程` still fails closed when only cross-region or third-party
   material is available; the LLM cannot relax the requirement.
4. Invalid or unavailable model assessment falls back deterministically and is
   persisted as such.
5. Fast, deterministic E2E, browser E2E, and an isolated live provider check
   cover the changed behavior without writing normal project or Demo data.

