# Wiki Workspace Iteration Spec

## Purpose

Move Domain Atlas from a Wiki-first knowledge layer toward a Karpathy-style / Obsidian-style LLM Wiki workspace. The current SQLite and Chroma layers remain the system of record. This iteration adds typed Wiki pages, stable workspace paths, special index/log/template pages, and a workspace browser UI.

## Problem

The current Wiki UI is a flat list of generated pages. It supports Wiki-first QA internally, but it does not yet feel like a browsable, maintainable LLM Wiki vault with `index`, `log`, source summaries, concept pages, synthesis pages, and templates.

## Requirements

- Preserve existing `wiki_pages`, `wiki_sections`, and `wiki_links`.
- Add compatible metadata for `page_type`, `path`, and `updated_at`.
- Support page types:
  - `index`
  - `log`
  - `source`
  - `concept`
  - `entity`
  - `synthesis`
  - `template`
  - `query` as a reserved type
- Ensure every build has at least:
  - `wiki/index`
  - `wiki/log`
  - `wiki/templates/source`
  - `wiki/templates/concept`
- Organize generated pages under paths like:
  - `wiki/sources/...`
  - `wiki/concepts/...`
  - `wiki/entities/...`
  - `wiki/synthesis/...`
  - `wiki/templates/...`
- `/domains/{project_id}/wiki` must render a workspace view:
  - index page first,
  - page type/path/revision/citations metadata,
  - type grouped navigation,
  - group labels for index, log, sources, concepts, entities, synthesis, templates, and queries.
- `/domains/{project_id}/wiki/{path:path}` may render one page if implementation stays small.
- QA remains Wiki-first and keeps source provenance behavior.
- This iteration will not export Markdown files. Markdown vault export is deferred to a later iteration and must be recorded as such.

## Layer Boundary

- Raw evidence remains in sources/chunks and runtime data storage.
- The Wiki workspace is stored in SQLite metadata and rendered through Web UI.
- Future export may project the same workspace into `data/projects/{project_id}/wiki/`, but this iteration does not make filesystem Markdown the source of truth.

## Acceptance Criteria

- New iteration SDD docs exist.
- MVP task index has Phase 15.
- Existing databases initialize without migration failure.
- `WikiPage` exposes `page_type`, `path`, and `updated_at`.
- Build workflow ensures index/log/source/concept/synthesis/template pages.
- Wiki UI displays workspace groups and page metadata.
- Deterministic E2E sees index, log, sources, concepts, synthesis, and templates.
- Existing QA and learning path behavior still works.
- Required tests and regression commands pass.
- Local commit is created; push remains deferred.
