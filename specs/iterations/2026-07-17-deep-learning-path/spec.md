# Deep Navigable Learning Path Spec

## Problem

The learning guide's mainline currently behaves as a short outline. It tells a learner
what to study, but does not lead them to the corresponding teaching content. The staged
modules are also too compressed: one or two short blocks cannot teach a learner enough
to understand a mechanism, follow a concrete example, and complete a basic practice.

## Goal

Turn the learning page into a navigable micro-textbook:

- the mainline explains the expected learning outcome and leads to a lesson chapter;
- each mainline node exposes related concepts and links to an existing Wiki concept page;
- each of the five lesson chapters contains enough Agent-authored, citation-grounded
  teaching material to stand on its own;
- source links remain provenance and optional deep reading, not the primary curriculum.

## Data Contract

`learning_guides.mainline_json` remains the persisted storage and gains optional fields:

- `module_stage`: the 1-based stage of the associated learning module;
- `learning_outcome`: the concrete capability or conclusion the learner should gain;
- `concept_names`: two to four related concept names.

`learning_modules` keeps its existing columns. Its structured content contract becomes:

- `stage_overview`: why this chapter belongs at this point;
- `core_explanation`: connected teaching prose, not a teaser;
- `knowledge_blocks`: three to five ordered blocks, each explaining a definition,
  mechanism, causal relation, or derivation;
- `examples`: at least one concrete end-to-end example or worked case;
- `misconceptions`: at least one real misconception or failure mode with a correction;
- `objectives`, `key_concepts`, `check_questions`, and `practice_task`: learner-facing
  reinforcement;
- `further_reading`: evidence and optional deep reading only.

The build prompt must specifically require the data-platform modeling chapter to cover
the problem it solves, business entities/activities/grain, dimensional and fact modeling,
metric derivation, an order-analysis example, and failure modes. The same teaching depth
is required of every stage.

## Compatibility

Existing databases require no new table or column. Payload normalization must derive a
safe stage mapping from mainline order and modules where it is missing, derive a learning
outcome from the old explanation, and derive concept names from module concepts. Existing
projects must render readable non-linked concept labels when a matching Wiki page does not
exist.

## UI

`/domains/{id}/path` should present the mainline as a compact navigation surface. Every
node shows its title, outcome, cited explanation, two to four concepts, and a link to
`#lesson-stage-{n}`. Every lesson chapter owns that stable id and renders the expanded
teaching sections before its evidence/deep-reading section.

## Verification

- Unit/application tests cover normalization, persistence, old-data fallback, anchors,
  concept links, and citations.
- The deterministic Playwright regression follows a mainline link, checks the destination
  contains lesson teaching content, opens a concept Wiki link, and validates desktop and
  mobile layout metrics.
- The live E2E regression validates five real modules, navigable mainline records,
  substantial teaching structure, and citations.
- Rebuild local project 2 (瓴羊Dataphin) and inspect the resulting learning page.
