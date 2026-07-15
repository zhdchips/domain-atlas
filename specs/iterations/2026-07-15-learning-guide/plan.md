# Learning Guide Upgrade Plan

1. Add SDD spec, plan, and tasks.
2. Extend SQLite schema with `learning_guides`.
3. Add repository dataclass, persistence, and retrieval for learning guides.
4. Update build prompt and payload validation to require `learning_guide`.
5. Update fake payloads and deterministic tests.
6. Redesign `learning_path.html` to show guide sections before modules.
7. Add CSS for guide layouts.
8. Extend browser E2E to check the learning guide page layout.
9. Run fast, browser-e2e, and live-e2e regressions.
10. Rebuild at least one local project to verify the rendered path page.
11. Commit locally without pushing.
