# LLM-led Project Intake Assessment

## Problem

The existing intake flow only recognises a small set of hard-coded terms, then asks an LLM to rewrite preselected options. It misses most semantically broad or ambiguous domains and does not let the model determine whether a clarification is useful.

## Scope

- Use one configured LLM completion at project creation to return a structured intake assessment.
- Let the model classify an input as `clear` or `clarify`, with a confidence score and a concise reason.
- For `clarify`, render one focused question and two or three learner-selectable scopes, including a recommended default.
- For `clear`, create the project immediately using the submitted domain name as its scope.
- Validate all model output before it changes navigation or persisted state.
- If the provider is unavailable, fails, returns invalid JSON, or reports insufficient confidence, create the project directly and record a non-sensitive fallback state.
- Preserve existing `needs_clarification` projects and their metadata rendering/confirmation behavior.

## Assessment Contract

The provider returns one JSON object with all of these fields:

```json
{
  "decision": "clear | clarify",
  "confidence": 0.0,
  "reason": "short explanation",
  "understanding": "short restatement that includes the submitted domain",
  "question": "one question or an empty string for clear",
  "options": [
    {"value": "stable_id", "label": "short label", "description": "why this angle", "scope": "concrete learning boundary"}
  ],
  "recommended_option": "stable_id or empty string for clear",
  "default_scope": "recommended scope or submitted domain for clear",
  "assumptions": ["up to three concise assumptions"]
}
```

For `clear`, `options` must be empty, `question` and `recommended_option` must be empty, and `default_scope` must equal the submitted domain. For `clarify`, the response must include two or three unique options, and `recommended_option` and `default_scope` must resolve to one of them. The supplied learner level is context only: no model output may alter it.

## Reliability And Ownership

- One assessment attempt only; no retry is performed by the intake provider.
- The assessment threshold is configurable. A low-confidence response is treated as unavailable and falls back to direct creation.
- The learner may select a recommendation, accept the default, or provide a custom scope. That confirmed choice is authoritative.
- Persist normalized assessment data, confidence, source and non-sensitive status. Do not persist prompts, raw responses, exceptions, provider URLs, or credentials.
- The old deterministic name profiles are removed from the primary path. Local code only validates input, validates the LLM response, and provides the direct-create fallback.

## Non-goals

- No multi-turn intake chat.
- No background work, search, ingestion, or build during intake.
- No live-LLM test in the default regression layers.

## Acceptance Criteria

1. Injected deterministic model responses can clarify `Agent`, `数据治理`, and `产品运营`, each with a meaningful single question and selectable scopes.
2. A clear `Dataphin` input reaches its dashboard immediately.
3. Invalid, low-confidence, unavailable, or timed-out model assessment never blocks project creation or exposes provider details.
4. Confirmation persists the learner-selected scope, original level, decision reason, assessment confidence, source/status, and selection metadata.
5. Existing clarification records continue to open and confirm successfully.
6. Unit, application, and Playwright checks cover the deterministic regression path, including mobile non-overflow.
