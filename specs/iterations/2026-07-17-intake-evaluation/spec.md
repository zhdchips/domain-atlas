# Intake Evaluation

## Problem

Intake assessment controls whether Domain Atlas interrupts a learner for clarification. Unit tests can prove JSON validation and fallback mechanics, but they cannot expose whether the configured model asks at the right time or proposes useful learning boundaries.

## Scope

- Add a versioned Chinese case set outside production code.
- Evaluate `clear` / `clarify` correctness, clarification structure, topic coverage, default consistency, sensitive-content safety, and fallback behavior.
- Provide a deterministic offline evaluator based on recorded structured assessments.
- Provide an opt-in live evaluator that calls the configured chat model exactly once per case and writes a non-sensitive JSON report.
- Add the deterministic evaluator to the fast regression layer and document ongoing case maintenance.

## Case Contract

Each case includes `id`, `core`, `category`, `name`, `goal`, `level`, `expected_decision`, optional `required_topics`, `notes`, and a recorded `offline_payload`. The recorded payload uses the production intake JSON contract so the offline layer validates the same boundary as production.

`required_topics` applies only to `clarify`. A live result passes this check when every required topic appears in at least one normalized candidate label, description, or scope. This deliberately checks semantic coverage rather than exact phrasing.

## Metrics And Gates

- `decision_accuracy`: matching expected decisions / all cases.
- `false_interrupt_rate`: expected clear returned clarify / expected clear cases.
- `false_pass_rate`: expected clarify returned clear or fallback / expected clarify cases.
- `clarification_structure_rate`: clarify results with 2-3 distinct candidates and a coherent default / clarify results.
- `topic_coverage_rate`: clarify results covering all required topics / clarify results with required topics.
- `fallback_safe_rate`: fallbacks that preserve the submitted domain as the direct scope / fallbacks.

Initial gate: all core cases pass, `decision_accuracy >= 0.85`, `clarification_structure_rate == 1.0`, and `topic_coverage_rate >= 0.80`. A live gate failure is an evaluation result, not a reason to silently edit the gold set.

## Live Safety

The live evaluator makes no web, ingestion, embedding, project, database, or build calls. It requires only `LLM_API_KEY`, `LLM_BASE_URL`, and `CHAT_MODEL`; it creates the same one-shot, no-retry chat provider as production intake. Reports include case ids, normalized decisions, confidence, elapsed time, check outcomes, metrics, and coarse failure categories. They never include prompts, raw responses, exception strings, API keys, provider URLs, or project data.

## Maintenance

- Add a case when a real learner input reveals a new class of decision mistake.
- Change a gold expectation only with a documented product-policy change, not to make a model score look better.
- Keep cases small, specific, and non-overlapping; tag the smallest representative set as `core`.
- Run offline evaluation with every intake change. Run live evaluation once after an intake/prompt/model/config change and compare its report with the prior recorded report.

## Non-goals

- The evaluator does not alter production intake behavior, prompt, threshold, or database records.
- It does not use an LLM-as-judge or claim that a small case set is a comprehensive measure of user experience.
