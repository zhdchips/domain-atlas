# Public Read-Only Demo Safety Plan

1. Add an explicit `public_demo_mode` setting and a first-request allowlist middleware. Skip normal local persistence initialization in this mode.
2. Create a repository-owned, in-memory catalog for one selected demo project. Reuse existing artifact data shapes so the Wiki and learning-path rendering remains representative without a database.
3. Add dedicated demo overview and cited-QA templates. Make existing Wiki and learning-path URL helpers prefix-aware so their presentation can be reused safely.
4. Add application and browser regression checks for route isolation, no-provider/no-data behavior, absence of mutable controls, and local-mode compatibility.
5. Document local versus public execution and the explicit future security work required before writable trials.

## Design Decisions

- Public mode is a separate runtime surface, not a permission flag on ordinary projects. This avoids accidental reads from the local database and makes the deployment boundary auditable.
- The catalog is in Python source rather than a seeded runtime database. Visitors therefore cannot create, update, or cross-contaminate Demo state.
- Only GET routes are allowlisted. Returning `404` rather than a redirect for mutable paths prevents probing users from discovering a mutable alternate surface.
- The Demo contains pre-generated QA rather than anonymous free-form QA, so its zero-provider-cost property holds even under arbitrary traffic.
