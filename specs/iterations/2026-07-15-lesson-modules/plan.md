# Lesson Module Upgrade Plan

1. Create SDD spec, plan, and tasks.
2. Extend `learning_modules` schema with lesson fields.
3. Add migration helpers for existing databases.
4. Extend `LearningModule` and repository persistence/retrieval.
5. Update build prompt and payload validation for lesson-style modules.
6. Update `/path` template and CSS to prioritize teaching content.
7. Update deterministic fake payloads and unit tests.
8. Extend browser E2E to inspect lesson-module layout.
9. Run fast, browser-e2e, and live-e2e regressions.
10. Rebuild one local project and inspect `/path`.
11. Commit locally without pushing.
