# LLM-assisted Intake Suggestions

## Problem

Deterministic intake correctly decides when to clarify, but its copy and choices are limited to a local profile registry. An LLM can improve wording and option descriptions when clarification is already necessary, provided it never decides whether to interrupt or expands the allowed project boundary.

## Scope

- Add an injectable `LLMIntakeSuggestionProvider` using the existing OpenAI-compatible chat interface.
- Call it at most once and only after a rule assessment returns `needs_clarification`.
- Strictly validate a small JSON overlay, then merge it into the rule assessment without changing `reason`, state, scope allowlist, or level mapping.
- Persist suggestion source/status only; do not persist prompts, raw responses, or provider errors.
- Fall back silently to rule suggestions for disabled, unconfigured, failed, or invalid providers.

## JSON contract

`understanding`, `question`, `options`, `default_scope`, and optional `assumptions`. Every option must retain one of the rule-provided `value`s and exactly the corresponding rule-provided `scope`; only presentational wording may change. Options must contain 2–3 unique valid entries.

## Non-goals

- The LLM does not classify clear inputs, change project data directly, or introduce a background worker.
- No live LLM regression is required because the feature defaults off.
