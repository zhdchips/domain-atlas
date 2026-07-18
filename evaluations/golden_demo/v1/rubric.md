# Golden Demo Manual Review Rubric

Run the deterministic evaluator first. This rubric covers the remaining
qualitative checks; it is deliberately not replaced by an LLM judge.

| Dimension | Pass condition | Evidence to inspect |
| --- | --- | --- |
| Source authority | Each source is first-party documentation or an engineering article published by the named organization. | Demo source cards and source URL. |
| Claim restraint | The content distinguishes documented facts from engineering recommendations and does not present vendor material as universal proof. | Ten-question overview, Wiki, QA. |
| Teaching value | A reader can explain why a harness exists, how a loop works, what tool contracts protect, and why Trace and evaluation differ. | Five learning modules and check questions. |
| Provenance | A reader can click source labels and Wiki labels from the relevant public page. | Source cards, Wiki, learning path, QA. |
| Honest uncertainty | The insufficient-evidence QA declines the unsupported claim without attaching a decorative citation. | QA example 5. |
| Portfolio clarity | The evaluation result is described as a fixed-catalog integrity check rather than a model benchmark or production metric. | Evaluation page and README. |

The reviewer records a date, reviewer role, outcome, and notes in
`manual-review.md`. Re-review source URLs when publishing a new release.
