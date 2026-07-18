# Source Selection Quality Spec

## Purpose

Prevent guided mode from turning a loosely related, duplicated, or low-quality public-web corpus into an apparently authoritative domain map. A one-click build must distinguish direct evidence from supplemental material, require direct evidence for branded service workflows, and explain when it cannot meet that bar.

## User Problem

The `寿司郎在线取号流程` case selected an open-source queue helper and its GitHub fork as two successful sources. They satisfied the two-URL build gate even though they are one evidence family and neither documents the operator's official process. The resulting Wiki accurately summarized the tool README, but answered a different question than the learner asked.

## Functional Requirements

### Candidate Assessment

- Enrich every discovered candidate with an explainable `source_role`, `source_family`, `selection_reason`, and `manual_warning` in its metadata. Roles are `first_party`, `primary_document`, `institution`, `paper`, `independent_coverage`, `community_tool`, `repository`, `mirror_or_fork`, and `unverified`.
- Keep source identity, scope relevance, direct-authority eligibility, and evidence-family independence separate. The numeric authority score remains a ranking input only.
- A GitHub repository is a `repository`, not an official document merely because it lives on `github.com`. It may be direct evidence for an explicitly open-source / SDK / repository scope, but is supplemental for a branded service workflow.
- Collapse exact URLs, known mirrors, same-name GitHub repositories, and explicit fork signals into one source family before guided ingestion. The highest-ranked representative remains available; other family members remain visible with a duplicate/fork explanation.

### Official-First Policy

- Detect branded-service workflow scopes using deterministic Chinese and English workflow signals, while excluding explicit open-source/tool/SDK/repository scopes.
- For an official-first scope, guided mode requires at least one candidate whose role is `first_party` or `primary_document` before it starts ingestion. If none exists, it must not silently build from supplemental material.
- The resulting workflow state is `evidence_insufficient`, with a Chinese reason, direct-source requirement, visible candidate assessment, and an actionable manual path.
- Expert/manual confirmation remains available for every candidate. Confirming a supplemental candidate records its role and warns the learner that it is not official-process evidence.
- Existing projects are never migrated, deleted, or rebuilt automatically.

### Independent Evidence Gate

- `MIN_BUILD_SOURCES` means two successful, distinct evidence families.
- The queue skips known duplicate-family candidates and continues to later candidates after an ingestion failure or post-ingestion duplicate rejection.
- After loading a URL, compare normalized content to previously ingested project sources. Exact and obvious near duplicates are excluded before chunk/vector persistence and do not satisfy the gate.
- The terminal outcome is either `minimum_independent_sources_reached`, `candidates_exhausted`, or `evidence_insufficient`. Persist the required role, selected families, skipped candidates, and attempted-source details in the workflow record.

### URL Content Quality

- HTML normalization excludes common non-content regions such as `nav`, `header`, `footer`, `aside`, forms, scripts, and styles.
- URL ingestion records deterministic text-quality signals. Sources that are too short or predominantly template/navigation text retain their raw and normalized artifacts but are marked excluded and do not emit chunks or embeddings.
- The quality check is local, deterministic, and does not alter Markdown/PDF ingestion semantics.

### UI And Compatibility

- The candidate list displays role, source family, selection reason, and a warning for supplemental / duplicate candidates.
- Workflow status renders the evidence-insufficient state separately from network or parse exhaustion, with a direct manual recovery action.
- Local Guided and Expert modes keep their existing routes. Public Demo remains zero-provider, zero-database, and read-only.

## Non-Goals

- No claim that domain heuristics can prove legal ownership of every website.
- No browser automation, CAPTCHA bypass, GitHub API dependency, or external classifier.
- No deletion of existing bad sources; this policy governs future guided runs and manual source annotations.

## Acceptance Criteria

1. A recorded `寿司郎在线取号流程` search containing an original GitHub helper, its fork, and news pages ends as `evidence_insufficient`, creates no automatic sources, and tells the learner that direct official material is missing.
2. A recorded open-source-tool scope can use an official repository plus a distinct project document to reach the independent two-family gate.
3. An official document plus an institution source builds successfully; duplicate/fork candidates do not count as a second source.
4. A near-duplicate URL source is excluded before chunks/vectors persist, while its raw artifact and quality reason remain inspectable.
5. Expert manual confirmation still allows supplemental material and records a learner-facing warning.
6. Fast, deterministic E2E, browser E2E, golden Demo, and one isolated live-guided run pass or report a precise external outcome without touching the user's normal database.
