# Lesson Module Upgrade Spec

## Problem

The current staged learning route still feels reading-list driven. A module has objectives, readings, concepts, questions, and one task, but the user must infer most knowledge from linked sources.

Domain Atlas should treat sources as evidence, not as the curriculum. The learning page should teach directly through Agent-generated, citation-grounded lesson content.

## Goal

Upgrade `learning_modules` into small textbook-like lesson chapters. Each stage should explain the topic, break knowledge into cited blocks, show examples and common misconceptions, then provide checks, practice, and optional evidence sources.

## Data Model

Keep the existing `learning_modules` table and add flexible columns:

- `stage_overview`: what this stage teaches and why it belongs here.
- `core_explanation`: compact self-contained teaching prose.
- `knowledge_blocks_json`: structured blocks with `title`, `body`, and `citations`.
- `examples_json`: example or case objects with `title`, `body`, and `citations`.
- `misconceptions_json`: misconception objects with `title`, `correction`, and `citations`.
- `further_reading_json`: optional source or Wiki references with `title`, `locator`, and `citations`.

Existing `objectives`, `readings`, `key_concepts`, `check_questions`, `practice_task`, and `citations` remain for compatibility. Old projects without the new fields should still render a useful page.

## Prompting

The build prompt must state:

- sources are evidence, not the curriculum;
- each learning module must be self-contained;
- readings become `further_reading`, not the primary learning unit;
- claims in lesson blocks, examples, and misconceptions should keep citations;
- output should remain compact and valid JSON.

## UI

`/domains/{id}/path` should prioritize each module's teaching content:

- stage orientation,
- core explanation,
- knowledge blocks,
- examples/cases,
- common misconceptions,
- key concepts,
- check questions,
- practice task,
- evidence sources / further reading.

The former "阅读材料" section should not be the main heading. Use "证据来源 / 深入阅读" for optional provenance and deep reading.

## Testing

Add or update tests for:

- schema migration for old databases,
- repository persistence and retrieval of lesson fields,
- build workflow fake payload with lesson fields,
- `/path` rendering of lesson blocks, examples, misconceptions, and evidence sources,
- browser E2E layout smoke for a lesson module.

## Acceptance

- New builds produce lesson-style modules.
- `/domains/{id}/path` teaches directly through Agent-generated content.
- Reading/source links are demoted to evidence or further reading.
- Old projects still open.
- Fast, browser-e2e, and live-e2e regressions pass.
- A local project rebuild shows the new lesson-style route.
