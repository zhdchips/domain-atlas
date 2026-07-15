# Learning Guide Upgrade Spec

## Problem

The current learning path is a five-stage outline. It tells users what to study next, but it does not first explain the domain itself. Users need a knowledge-rich guide that answers foundational questions before presenting a route.

## Goal

Upgrade Domain Atlas learning paths into a domain learning guide. The page should first answer core domain questions, then show the mainline, essential concepts, branch topics, and finally the staged learning route.

## Target Shape

Each generated project should include one `learning_guide` object and five `learning_modules`.

`learning_guide` contains:

- `summary`: concise domain orientation.
- `question_answers`: answers to what it is, why it exists, how it works, components, schools/types, representative people or organizations, classic cases, best practices, failure cases, and future trends.
- `mainline`: the main narrative a learner should follow.
- `core_concepts`: required concepts with short explanations and dependencies.
- `branches`: side paths, application scenarios, methods, or toolchains.
- `details`: deeper topics, practice directions, or advanced nuances.
- `citations`: source citations used by the guide.

`learning_modules` remain the staged route and should reference the guide's mainline and core concepts.

## Data Model

Add a `learning_guides` table with one row per project. Store structured sections as JSON to keep the MVP flexible and avoid over-normalizing guide content too early.

Old projects without a guide must still render. The UI should show a muted empty-guide note and still display existing modules.

## Prompting

The build prompt must request a compact `learning_guide` object with cited, evidence-grounded answers. It must avoid generic motivational advice. The LLM should answer from the provided chunks only.

The prompt should keep output bounded:

- exactly ten question answers,
- 5 to 8 mainline steps,
- 8 to 12 core concepts,
- 3 to 6 branches,
- 3 to 6 details,
- exactly five learning modules.

## UI

`/domains/{id}/path` should show:

- domain guide summary,
- key question answers,
- domain mainline,
- core concepts,
- branches and details,
- staged learning route.

The page should be scannable and not just a long bullet dump.

## Testing

Add tests for:

- learning guide persistence and old-database migration,
- build workflow persistence of `learning_guide`,
- learning path page rendering guide sections,
- browser E2E path layout smoke.

Run:

- `uv run python scripts/regression.py --fast`
- `uv run python scripts/regression.py --browser-e2e`
- `uv run python scripts/regression.py --live-e2e`

## Acceptance

- New builds generate `learning_guide`.
- Existing projects still open.
- `/domains/{id}/path` clearly displays guide sections and the staged route.
- Required regressions pass.
