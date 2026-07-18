# Golden Demo Evaluation Report

- Status: **PASS**
- Manifest: `golden-demo-evaluation/v1`
- Run date (UTC): 2026-07-18
- Score: 25 / 25 (gate: 25)
- Execution: deterministic, 0 provider calls, estimated cost $0.00

## Case Results

| ID | Category | Result | Detail |
| --- | --- | --- | --- |
| SRC-01 | source_authority | pass | source_count matched expected value. |
| SRC-02 | source_authority | pass | source_metadata_complete matched expected value. |
| SRC-03 | source_authority | pass | source_urls_are_https matched expected value. |
| SRC-04 | source_authority | pass | source_citations_are_unique matched expected value. |
| SRC-05 | provenance | pass | source_locators_are_https matched expected value. |
| WIKI-01 | wiki | pass | wiki_page_count matched expected value. |
| WIKI-02 | wiki | pass | required_page_types matched expected value. |
| WIKI-03 | wiki | pass | wiki_paths_are_unique matched expected value. |
| WIKI-04 | provenance | pass | wiki_citations_resolve matched expected value. |
| WIKI-05 | wiki | pass | wiki_links_resolve matched expected value. |
| GUIDE-01 | learning_guide | pass | ten_domain_questions matched expected value. |
| GUIDE-02 | learning_guide | pass | guide_question_citations_resolve matched expected value. |
| GUIDE-03 | learning_guide | pass | mainline_stages_are_complete matched expected value. |
| GUIDE-04 | learning_guide | pass | core_concept_count matched expected value. |
| GUIDE-05 | learning_guide | pass | branches_and_details_present matched expected value. |
| COURSE-01 | learning_modules | pass | module_count matched expected value. |
| COURSE-02 | learning_modules | pass | module_stages_are_complete matched expected value. |
| COURSE-03 | learning_modules | pass | modules_are_substantive matched expected value. |
| COURSE-04 | learning_modules | pass | module_citations_resolve matched expected value. |
| QA-01 | cited_qa | pass | qa_count matched expected value. |
| QA-02 | cited_qa | pass | supported_qa_has_evidence matched expected value. |
| QA-03 | cited_qa | pass | insufficient_qa_is_honest matched expected value. |
| DEMO-01 | demo_navigation | pass | demo_routes_are_complete matched expected value. |
| DEMO-02 | demo_navigation | pass | citation_links_are_complete matched expected value. |
| DEMO-03 | demo_navigation | pass | evaluation_summary_matches_manifest matched expected value. |

## Known Limitations

- This deterministic suite verifies one curated Demo catalog, not generic model, retrieval, or RAG quality.
- It does not fetch source URLs, so external availability and future page changes require periodic human review.
- It does not measure a live provider build; live E2E is reported separately.
