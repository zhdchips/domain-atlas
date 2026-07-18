# Changelog

All notable changes to this project are documented here.

## [0.1.0] - 2026-07-18

### Added

- Guided and Expert domain-learning workflows with URL, Markdown, and PDF ingestion.
- Evidence-backed LLM Wiki, concept relationships, learning paths, and Wiki-first cited QA.
- Public read-only Demo with a versioned golden evaluation catalog.
- Deterministic unit, E2E, browser, and golden-Demo regression layers.
- Source selection quality gates, regional official-entry provenance, and failure recovery states.

### Security Notes

- The public Demo is intentionally read-only and makes no provider calls.
- A writable public deployment still requires authentication, quota/rate-limit,
  tenant isolation, and further SSRF/upload hardening.
