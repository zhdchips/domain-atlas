from __future__ import annotations

from domain_atlas.domain.artifacts import WikiPage, WikiSection
from domain_atlas.domain.sources import Source
from domain_atlas.wiki.presentation import build_local_context, render_markdown, render_wiki_page


def test_markdown_renderer_supports_readable_blocks_and_safe_links():
    page = _page(
        page_id=1,
        slug="agent-loop",
        path="wiki/concepts/agent-loop",
        title="Agent Loop",
        body_markdown="# Agent Loop\n\nParagraph with **bold**, *italic*, and `code`.\n\n- one\n- two\n\n> quote\n\n```python\nprint('ok')\n```\n\n---\n\n[docs](https://example.com/docs)",
    )
    context = build_local_context(pages=[page], sections=[], sources=[], route_base="/domains/7/wiki")

    rendered = render_markdown(page.body_markdown, context=context, page_path=page.path)

    assert '<h1 id="heading-' in rendered.html
    assert "<strong>bold</strong>" in rendered.html
    assert "<em>italic</em>" in rendered.html
    assert "<ul>" in rendered.html
    assert "<blockquote>" in rendered.html
    assert "<pre><code" in rendered.html
    assert '<a href="https://example.com/docs">docs</a>' in rendered.html


def test_markdown_renderer_escapes_html_and_rejects_dangerous_urls():
    page = _page(page_id=1, slug="safe", path="wiki/concepts/safe", title="Safe", body_markdown="")
    context = build_local_context(pages=[page], sections=[], sources=[], route_base="/domains/7/wiki")

    rendered = render_markdown(
        '<script>alert(1)</script><img src=x onerror="alert(2)"> [bad](javascript:alert(3)) [good](https://example.com)',
        context=context,
        page_path=page.path,
    )

    assert "<script" not in rendered.html
    assert "<img" not in rendered.html
    assert ' onerror="' not in rendered.html
    assert "onerror=&quot;" in rendered.html
    assert 'href="javascript:' not in rendered.html
    assert 'href="https://example.com"' in rendered.html


def test_internal_wiki_links_resolve_title_alias_and_path_only_within_context():
    first = _page(page_id=1, slug="agent-loop", path="wiki/concepts/agent-loop", title="Agent Loop", body_markdown="")
    second = _page(page_id=2, slug="tools", path="wiki/concepts/tools", title="Tool Contracts", body_markdown="")
    context = build_local_context(pages=[first, second], sections=[], sources=[], route_base="/domains/7/wiki")

    rendered = render_markdown(
        "[[Agent Loop]] [[Tool Contracts|工具契约]] [[wiki/concepts/tools]] [[https://example.com]]",
        context=context,
        page_path=first.path,
    )

    assert 'href="/domains/7/wiki/concepts/agent-loop">Agent Loop</a>' in rendered.html
    assert 'href="/domains/7/wiki/concepts/tools">工具契约</a>' in rendered.html
    assert 'href="/domains/7/wiki/concepts/tools">wiki/concepts/tools</a>' in rendered.html
    assert "wiki-link-unresolved" in rendered.html
    assert "https://example.com" not in rendered.html.split("wiki-link-unresolved", 1)[0]


def test_ambiguous_wiki_link_is_inert_instead_of_guessing_a_target():
    first = _page(page_id=1, slug="agent-a", path="wiki/concepts/agent-a", title="Agent", body_markdown="")
    second = _page(page_id=2, slug="agent-b", path="wiki/concepts/agent-b", title="Agent", body_markdown="")
    context = build_local_context(pages=[first, second], sections=[], sources=[], route_base="/domains/7/wiki")

    rendered = render_markdown("See [[Agent]].", context=context, page_path=first.path)

    assert "wiki-link-unresolved" in rendered.html
    assert "/domains/7/wiki/concepts/agent-" not in rendered.html


def test_citations_resolve_to_scoped_source_and_renderable_wiki_section():
    page = _page(
        page_id=1,
        slug="agent-loop",
        path="wiki/concepts/agent-loop",
        title="Agent Loop",
        body_markdown="# Agent Loop\n\n## Definition\n\nEvidence [S1-C1] and [W:agent-loop#1].",
        citations=["S1-C1", "W:agent-loop#1"],
    )
    source = _source(source_id=1, title="Official Agent Docs", locator="https://example.com/agent")
    section = WikiSection(
        id=1,
        section_uid="agent-loop#1",
        project_id=7,
        page_id=1,
        page_slug="agent-loop",
        heading="Definition",
        ordinal=1,
        body_markdown="Evidence.",
        citations=["W:agent-loop#1"],
        source_chunk_uids=["chunk:1"],
        source_citation_labels=["S1-C1"],
        links=[],
        page_path=page.path,
    )
    context = build_local_context(
        pages=[page],
        sections=[section],
        sources=[source],
        route_base="/domains/7/wiki",
    )

    rendered = render_wiki_page(page, context)

    assert 'href="https://example.com/agent"' in rendered.body_html
    assert 'href="/domains/7/wiki/concepts/agent-loop#section-1"' in rendered.body_html
    assert 'id="section-1"' in rendered.body_html
    assert [citation.title for citation in rendered.evidence] == ["Official Agent Docs", "Agent Loop"]


def test_local_upload_citation_is_visible_but_never_exposes_a_file_path():
    page = _page(page_id=1, slug="upload", path="wiki/sources/upload", title="Upload", body_markdown="[S2-C1]")
    source = _source(source_id=2, title="Private Upload", locator="/private/path/document.md")
    context = build_local_context(pages=[page], sections=[], sources=[source], route_base="/domains/7/wiki")

    rendered = render_wiki_page(page, context)

    assert "citation-unresolved" in rendered.body_html
    assert "/private/path/document.md" not in rendered.body_html


def _page(
    *,
    page_id: int,
    slug: str,
    path: str,
    title: str,
    body_markdown: str,
    citations: list[str] | None = None,
) -> WikiPage:
    return WikiPage(
        id=page_id,
        project_id=7,
        slug=slug,
        page_type="concept",
        path=path,
        title=title,
        topic_path=path,
        summary="Summary [S1-C1]",
        body_markdown=body_markdown,
        citations=citations or [],
        revision=1,
        created_at="2026-07-18T00:00:00Z",
        updated_at="2026-07-18T00:00:00Z",
    )


def _source(*, source_id: int, title: str, locator: str) -> Source:
    return Source(
        id=source_id,
        project_id=7,
        source_type="url",
        title=title,
        locator=locator,
        raw_path="",
        normalized_path="",
        checksum="",
        status="ingested",
        metadata={},
        created_at="2026-07-18T00:00:00Z",
        updated_at="2026-07-18T00:00:00Z",
    )
