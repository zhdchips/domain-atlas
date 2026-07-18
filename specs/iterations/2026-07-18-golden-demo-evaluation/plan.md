# Golden Demo and Evaluation Plan

1. Define the source and scoring contract before changing the catalog. Keep the
   scoring manifest separate from application code so it can be audited.
2. Expand the in-memory catalog with source metadata, stronger teaching content,
   a source-backed failure case, and a deliberately evidence-insufficient QA.
3. Add citation-link mapping and a read-only evaluation page while retaining the
   existing public-mode allowlist and no-write boundary.
4. Implement a deterministic evaluator with explicit assertion handlers and
   versioned fixture, rubric, manual-review record, and baseline report.
5. Add unit and browser regressions, run the layered suite, then run one
   isolated live build E2E only as a separately reported provider smoke check.

## Design Decisions

- The catalog stays as Python source because public mode must not create or read
  a seeded runtime database. Evaluation assets are JSON and Markdown because
  they need stable review diffs.
- The score measures Demo integrity and evidence traceability, not generative
  answer quality. Therefore it is deterministic and does not use an LLM judge.
- Citation links preserve the existing human-readable labels (`S1-C1` and
  `W:slug#1`) while making the evidence path inspectable in the UI.
- The static evaluation page shows the committed baseline. The evaluator is the
  authority; UI metrics are not independently calculated in the browser.
