# Source Selection Quality Plan

## Architecture

Candidate assessment is a pure domain service. It accepts the project scope and discovery drafts, returns enriched immutable drafts plus a policy decision, and stores the explanation in candidate metadata. FastAPI only calls the service and templates only render its fields.

Guided Autopilot consumes a `SelectionPlan`. Its official-first gate runs before source creation. Its queue contains one representative per evidence family and it records structured selection/skip state. Ingestion owns document normalization, local quality scoring, and post-load duplicate detection before it writes chunks or vectors.

Manual confirmation does not use the guided policy gate: it preserves learner control, but copies the candidate assessment into source provenance and renders a warning.

## Implementation Steps

1. Add the pure source-assessment module, candidate metadata helpers, source-family normalization, and official-first policy decision.
2. Integrate assessment into Exa discovery persistence, manual discovery, Autopilot selection, source metadata, and dashboard rendering.
3. Refactor Autopilot to require direct evidence when needed and count successful source families rather than URLs.
4. Improve HTML normalization and add local content quality / near-duplicate rejection before chunk/vector writes.
5. Add structured workflow outcomes, UI recovery copy, deterministic fixtures, browser checks, and isolated live-guided reporting.

## Design Decisions

- `primary_document` represents a deterministic direct-document signal such as an official/help/developer document. It is intentionally not a legal assertion that every `docs.*` host belongs to the named brand.
- GitHub family grouping uses a conservative repository-name family plus explicit fork/mirror words. It can occasionally group unrelated same-name repositories, which is safer than falsely treating forks as independent evidence.
- Quality rejection preserves raw/normalized artifacts and an exclusion reason. It avoids creating chunks, vectors, or an accidental build context from page chrome.
- The scope policy fails closed only for service-workflow signals; broad educational domains retain the existing fallback behavior.

## Risks

- Search engines may not surface official material. The correct outcome is a visible evidence gap and a manual path, not a weaker automatic build.
- Near-duplicate detection is heuristic. Exact hashes and clear high-overlap texts are rejected; borderline similarity stays visible for manual review.
- Live search rankings remain non-deterministic, so recorded tests prove policy while the live run is compatibility evidence only.
