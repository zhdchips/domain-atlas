# Readable Wiki Rendering Plan

1. Add a direct Markdown parser dependency and a pure presentation module for
   Markdown, internal links, citations, and source evidence.
2. Build a context factory from local Wiki pages/sections/sources and reuse the
   same data shape for the in-memory public Demo catalog.
3. Replace raw Wiki-body rendering with safe rendered HTML and an evidence
   panel. Use inline rendering for the learning-guide overview/questions and QA
   answers that embed citation labels.
4. Add unit tests for parsing, sanitization, scoping, missing/ambiguous links,
   local routes, and Demo isolation. Expand browser checks for real navigation
   and responsive content layout.

## Design Decisions

- `markdown-it-py` is a mature parser already present transitively, but becomes
  a direct dependency because the application imports it.
- Raw HTML remains disabled, rather than sanitizing arbitrary generated HTML
  after the fact. Custom wikilinks and citations are parser tokens rendered only
  from resolver-approved targets.
- Section hashes are opportunistic: a citation points to `#section-N` only when
  the generated page contains the matching heading; otherwise it safely targets
  the page top.
- Unresolved references preserve reader context but never become guessed links.
