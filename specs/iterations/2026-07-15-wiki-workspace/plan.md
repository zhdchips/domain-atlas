# Wiki Workspace Iteration Plan

## Approach

Keep the current persistence model and add a workspace projection inside `wiki_pages`. This avoids a risky rewrite while moving the product shape closer to the Karpathy-style markdown vault pattern.

## Steps

1. Add iteration SDD files and MVP Phase 15 index.
2. Add database columns:
   - `wiki_pages.page_type`
   - `wiki_pages.path`
   - `wiki_pages.updated_at`
3. Extend `WikiPage` and artifact repository read/write paths.
4. Add workspace normalization helpers that:
   - infer missing page type/path,
   - add source pages from `source_profiles`,
   - add concept pages from `concepts`,
   - add a synthesis page if missing,
   - add index/log/template pages.
5. Update build prompt to request typed Wiki pages and paths.
6. Update Wiki UI:
   - `/domains/{id}/wiki` grouped workspace view,
   - optional `/domains/{id}/wiki/{path:path}` page view.
7. Update tests:
   - schema/repository metadata,
   - build workflow workspace pages,
   - Wiki UI grouping and metadata,
   - deterministic E2E.
8. Run regression gates and commit locally.

## Deferred

Markdown vault export to `data/projects/{project_id}/wiki/` is deferred. The Web workspace will carry the vault organization first; export can become a later projection of the same page metadata.

## Risks

- LLM payloads may omit typed metadata. Mitigation: code-level workspace normalization.
- Existing tests assume simple pages. Mitigation: default old pages to `concept` and paths to `wiki/concepts/{slug}`.
- Existing project data may have old schema. Mitigation: compatibility migrations via `_ensure_column` before dependent indexes.
