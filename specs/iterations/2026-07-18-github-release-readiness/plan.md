# GitHub Release Readiness Plan

1. Audit the current repository, README, ignores, environment template,
   packaging, and regression entry points.
2. Create deterministic public-Demo screenshots through Playwright and use
   them in a rewritten README with an ASCII Mermaid architecture diagram.
3. Add the license, contribution guide, changelog, release notes, Docker
   artifacts, and CI workflow.
4. Build the image and run the public-Demo container. Run all deterministic
   regression layers and scan tracked content for release blockers.

## Design Decisions

- Screenshots use public-Demo content, not mutable local user data or provider
  credentials.
- CI never has Exa, LLM, or embedding credentials. Live checks remain opt-in
  developer verification.
- Container persistence is opt-in through `/app/data`; the public Demo runs
  without runtime data and remains read-only.
- The remote checklist is documentation only because this iteration must not
  push, alter the remote default branch, or create a Release.
