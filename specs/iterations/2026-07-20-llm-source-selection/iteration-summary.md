# LLM-Assisted Source Selection Summary

## Delivered

- `source_policy` now owns deterministic hard gates only. A broad learning
  candidate is no longer rejected solely because a URL/type heuristic produced
  a score below `0.50`.
- `candidate_assessment` adds a bounded, strict-schema batch LLM assessment for
  relevance, authority, coverage, risks, priority, and optional supplemental
  queries. The model cannot create URLs, set first-party status, change regions,
  or relax direct-authority requirements.
- Guided Autopilot keeps up to six legal candidates, consumes them until two
  independent source families ingest successfully, and makes at most one
  normal-domain supplemental-search round from validated model queries.
- Model failures, invalid responses, and low confidence explicitly fall back to
  deterministic ranking. Candidate, workflow, and source provenance preserve
  the assessment source/status and explanation.
- The dashboard distinguishes semantic assessment, supplemental search,
  low-quality discovery, direct-authority gaps, and source exhaustion.

## Requirement Audit

| Requirement | Evidence |
| --- | --- |
| Hard gates remain deterministic | `source_policy` tests and the service-workflow `MustNotBeCalledAssessmentProvider` regression prove LLM assessment cannot run before a missing direct-authority gate. |
| LLM assessment is bounded and validated | `tests/test_candidate_assessment.py` covers complete batches, unknown IDs, unsafe queries, invalid results, low confidence, ranking, and deterministic fallback. |
| Low-score broad-domain sources are not pre-rejected | `test_broad_learning_scope_keeps_low_heuristic_score_web_candidates_for_semantic_assessment` and the recorded self-media workflow case. |
| One supplemental round is budgeted | The recorded self-media workflow asserts exactly one extra query and successful queue formation. |
| Candidate failures can use later candidates | The existing recorded travel-agent E2E and Autopilot fallback tests continue to assert queue consumption after blocked sources. |
| Service workflows fail closed | Source-policy, regional, and Autopilot tests preserve the direct-authority and cross-region behavior. |
| UI states are visible | Playwright fixture asserts LLM-ranked queue and supplemental-search progress; browser regression also keeps exhaustion and official-evidence feedback. |
| Normal data remains untouched | Deterministic checks use temporary data directories; live-guided preserves its own temporary workdir on failure. |

## Residual External Risk

Search ranking, anti-bot access controls, and model JSON compliance remain
external variables. The new candidate layer degrades safely for the first two;
the live check still exposed the separate knowledge-build JSON reliability gap,
which should be addressed by a future bounded JSON-repair/build decomposition
iteration.
