# Readable Wiki Rendering Spec

## Purpose

Render generated Wiki Markdown as a safe, navigable knowledge workspace rather
than raw text, while keeping each project's links and provenance isolated.

## Rendering Model

- Use `markdown-it-py` as a direct dependency with raw HTML disabled and a
  strict `http`, `https`, and `mailto` URL allowlist for ordinary Markdown
  links. The renderer never trusts raw model HTML.
- Render Markdown into a request-scoped view model. It contains safe HTML,
  resolved citations, unresolved internal links, and stable heading anchors.
- Support headings, paragraphs, ordered and unordered lists, emphasis, block
  quotes, inline code, fenced code blocks, horizontal rules, and safe Markdown
  links.
- Every rendered heading has a deterministic `heading-...` id. A WikiSection
  heading that can be matched unambiguously receives `section-{ordinal}` so a
  Wiki citation may target it.

## Internal Links and Citations

- `[[Title]]`, `[[Title|Alias]]`, and `[[wiki/path]]` resolve only against the
  current catalog/project's Wiki pages. A resolved link uses the supplied Wiki
  route base; an unresolved or ambiguous one becomes readable inert text with a
  `wiki-link-unresolved` class.
- Source labels (`S#-C#`) resolve only to a real source in the current project.
  HTTP(S) sources link to their locator; local upload sources remain a visible,
  non-clickable source reference instead of exposing a file path.
- Wiki labels (`W:slug#ordinal`) resolve only to a current Wiki page. They use
  a section hash when that section's heading can be rendered, otherwise the
  target page's top.
- A page evidence panel lists the current page's resolved source/wiki citations
  with title, type, and safe external-link behavior. Missing labels remain
  explicit and do not acquire invented targets.

## Reuse and Boundaries

- Local-first routes provide page, section, and source data to the shared
  presentation builder. Public Demo provides its in-memory pages and source
  catalog through the same builder; it still opens no database or provider.
- Rendered output is request-only. No Markdown, link target, or citation result
  is persisted back to SQLite or used as a provider prompt.
- Existing QA and learning-path citation metadata remains intact. Their key
  prose fields use the same inline renderer so embedded labels become links.

## Acceptance Criteria

- Wiki pages show semantic rendered HTML and no raw Markdown `<pre>` body.
- Dangerous HTML, event attributes, and `javascript:` links are not executable
  or rendered as trusted HTML.
- Local and Demo pages resolve internal Wiki links and source/Wiki citations to
  the correct scoped targets; broken links are inert and visible.
- Browser regression confirms rendering, route navigation, citation hrefs,
  absence of writable Demo controls, and mobile/desktop overflow safety.
- Deterministic fast, E2E, browser, and golden Demo evaluation suites pass.
