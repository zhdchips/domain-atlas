"""Safe, scoped Markdown presentation for Wiki pages and evidence labels."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from markdown_it import MarkdownIt
from markupsafe import Markup

from domain_atlas.domain.artifacts import WikiPage, WikiSection
from domain_atlas.domain.sources import Source


_SOURCE_CITATION_RE = re.compile(r"^S(?P<source_id>\d+)-C\d+$")
_WIKI_CITATION_RE = re.compile(r"^W:(?P<slug>[a-z0-9-]+)#(?P<ordinal>\d+)$")
_INLINE_CITATION_RE = re.compile(r"\[(S\d+-C\d+|W:[a-z0-9-]+#\d+)\]")
_SAFE_EXTERNAL_SCHEMES = ("http://", "https://", "mailto:")


@dataclass(frozen=True)
class CitationView:
    label: str
    title: str
    source_type: str
    href: str | None
    external: bool
    resolved: bool


@dataclass(frozen=True)
class RenderedMarkdown:
    html: Markup
    citation_labels: tuple[str, ...]


@dataclass(frozen=True)
class RenderedWikiPage:
    body_html: Markup
    summary_html: Markup
    evidence: tuple[CitationView, ...]


@dataclass(frozen=True)
class _PageTarget:
    title: str
    slug: str
    path: str
    href: str


class WikiPresentationContext:
    """Resolve Markdown references exclusively inside one Wiki namespace."""

    def __init__(
        self,
        *,
        pages: Iterable[WikiPage],
        route_base: str,
        sources: Iterable[Source] = (),
        sections: Iterable[WikiSection] = (),
        citation_views: Iterable[CitationView] = (),
    ) -> None:
        self.route_base = route_base.rstrip("/")
        self.pages = tuple(pages)
        self._page_targets = tuple(
            _PageTarget(
                title=page.title,
                slug=page.slug,
                path=page.path,
                href=f"{self.route_base}/{page.path.removeprefix('wiki/')}",
            )
            for page in self.pages
        )
        self._source_by_id = {source.id: source for source in sources}
        self._citation_views = {view.label: view for view in citation_views}
        self._wiki_citation_hrefs, self._section_heading_anchors = _section_targets(
            pages=self.pages,
            sections=tuple(sections),
            route_base=self.route_base,
        )

    @classmethod
    def for_demo(
        cls,
        *,
        pages: Iterable[WikiPage],
        route_base: str,
        citation_links: dict[str, str],
        citation_details: dict[str, tuple[str, str]],
    ) -> "WikiPresentationContext":
        views = [
            CitationView(
                label=label,
                title=citation_details.get(label, (label, "Wiki"))[0],
                source_type=citation_details.get(label, (label, "Wiki"))[1],
                href=href if _is_safe_href(href) else None,
                external=href.startswith(("http://", "https://")),
                resolved=_is_safe_href(href),
            )
            for label, href in citation_links.items()
        ]
        return cls(pages=pages, route_base=route_base, citation_views=views)

    def resolve_wikilink(self, target: str) -> _PageTarget | None:
        normalized = _normalize_reference(target)
        candidates = {
            page.href
            for page in self._page_targets
            if normalized
            in {
                _normalize_reference(page.title),
                _normalize_reference(page.slug),
                _normalize_reference(page.path),
                _normalize_reference(page.path.removeprefix("wiki/")),
            }
        }
        if len(candidates) != 1:
            return None
        return next(page for page in self._page_targets if page.href in candidates)

    def resolve_citation(self, label: str) -> CitationView:
        known = self._citation_views.get(label)
        if known is not None:
            return known

        source_match = _SOURCE_CITATION_RE.match(label)
        if source_match:
            source = self._source_by_id.get(int(source_match.group("source_id")))
            if source is not None:
                href = source.locator if _is_safe_external_href(source.locator) else None
                return CitationView(
                    label=label,
                    title=source.title,
                    source_type=source.source_type,
                    href=href,
                    external=href is not None,
                    resolved=True,
                )

        wiki_match = _WIKI_CITATION_RE.match(label)
        if wiki_match:
            page = next((item for item in self._page_targets if item.slug == wiki_match.group("slug")), None)
            if page is not None:
                href = self._wiki_citation_hrefs.get(label, page.href)
                return CitationView(
                    label=label,
                    title=page.title,
                    source_type="wiki",
                    href=href,
                    external=False,
                    resolved=True,
                )

        return CitationView(
            label=label,
            title="未解析引用",
            source_type="unresolved",
            href=None,
            external=False,
            resolved=False,
        )

    def heading_anchor(self, page_path: str, heading: str, occurrence: int) -> str:
        section_anchor = self._section_heading_anchors.get((page_path, _normalize_heading(heading)))
        if section_anchor and occurrence == 1:
            return section_anchor
        return f"heading-{_stable_id(heading)}" + (f"-{occurrence}" if occurrence > 1 else "")


def build_local_context(
    *,
    pages: Iterable[WikiPage],
    sections: Iterable[WikiSection],
    sources: Iterable[Source],
    route_base: str,
) -> WikiPresentationContext:
    return WikiPresentationContext(
        pages=pages,
        sections=sections,
        sources=sources,
        route_base=route_base,
    )


def render_wiki_page(page: WikiPage, context: WikiPresentationContext) -> RenderedWikiPage:
    body = render_markdown(page.body_markdown, context=context, page_path=page.path)
    summary = render_inline(page.summary, context=context)
    labels = _ordered_unique((*page.citations, *body.citation_labels, *summary.citation_labels))
    return RenderedWikiPage(
        body_html=body.html,
        summary_html=summary.html,
        evidence=tuple(context.resolve_citation(label) for label in labels),
    )


def render_markdown(
    markdown: str,
    *,
    context: WikiPresentationContext,
    page_path: str,
) -> RenderedMarkdown:
    parser = _markdown_parser(context=context, page_path=page_path)
    tokens = parser.parse(markdown)
    _assign_heading_anchors(tokens, context=context, page_path=page_path)
    return RenderedMarkdown(
        html=Markup(parser.renderer.render(tokens, parser.options, {})),
        citation_labels=tuple(_citation_labels(tokens)),
    )


def render_inline(markdown: str, *, context: WikiPresentationContext) -> RenderedMarkdown:
    parser = _markdown_parser(context=context, page_path="")
    tokens = parser.parseInline(markdown)
    return RenderedMarkdown(
        html=Markup(parser.renderer.render(tokens, parser.options, {})),
        citation_labels=tuple(_citation_labels(tokens)),
    )


def render_citation_list(labels: Iterable[str], *, context: WikiPresentationContext) -> Markup:
    if isinstance(labels, str):
        labels = [labels]
    rendered: list[str] = []
    for label in _ordered_unique(labels):
        citation = context.resolve_citation(label)
        safe_label = html.escape(citation.label)
        if citation.href is None:
            rendered.append(
                f'<span class="citation-link citation-unresolved" title="{html.escape(citation.title)}">{safe_label}</span>'
            )
            continue
        target = ' target="_blank" rel="noreferrer"' if citation.external else ""
        rendered.append(
            f'<a class="citation-link" href="{html.escape(citation.href, quote=True)}"{target}>{safe_label}</a>'
        )
    return Markup(", ".join(rendered))


def _markdown_parser(*, context: WikiPresentationContext, page_path: str) -> MarkdownIt:
    parser = MarkdownIt("commonmark", {"html": False, "linkify": False})
    parser.validateLink = _is_safe_external_href
    parser.inline.ruler.before("link", "wiki_link", _wiki_link_rule)
    parser.inline.ruler.before("link", "citation", _citation_rule)

    def render_wiki_link(tokens, index, options, env):
        target = str(tokens[index].meta["target"])
        label = str(tokens[index].meta["label"])
        resolved = context.resolve_wikilink(target)
        safe_label = html.escape(label)
        if resolved is None:
            return f'<span class="wiki-link-unresolved" title="未解析 Wiki 链接：{html.escape(target)}">{safe_label}</span>'
        return f'<a class="wiki-link" href="{html.escape(resolved.href, quote=True)}">{safe_label}</a>'

    def render_citation(tokens, index, options, env):
        label = str(tokens[index].meta["label"])
        citation = context.resolve_citation(label)
        safe_label = html.escape(label)
        if citation.href is None:
            return f'<span class="citation-link citation-unresolved" title="{html.escape(citation.title)}">{safe_label}</span>'
        target = ' target="_blank" rel="noreferrer"' if citation.external else ""
        return f'<a class="citation-link" href="{html.escape(citation.href, quote=True)}"{target}>{safe_label}</a>'

    parser.renderer.rules["wiki_link"] = render_wiki_link
    parser.renderer.rules["citation"] = render_citation
    return parser


def _wiki_link_rule(state, silent: bool) -> bool:
    if not state.src.startswith("[[", state.pos):
        return False
    end = state.src.find("]]", state.pos + 2)
    if end < 0:
        return False
    raw = state.src[state.pos + 2 : end].strip()
    if not raw:
        return False
    target, separator, display = raw.partition("|")
    target = target.strip()
    display = display.strip() if separator else target
    if not target or not display:
        return False
    if not silent:
        token = state.push("wiki_link", "", 0)
        token.meta = {"target": target, "label": display}
    state.pos = end + 2
    return True


def _citation_rule(state, silent: bool) -> bool:
    match = _INLINE_CITATION_RE.match(state.src, state.pos)
    if match is None:
        return False
    if not silent:
        token = state.push("citation", "", 0)
        token.meta = {"label": match.group(1)}
    state.pos += len(match.group(0))
    return True


def _assign_heading_anchors(tokens, *, context: WikiPresentationContext, page_path: str) -> None:
    occurrences: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or index + 1 >= len(tokens):
            continue
        heading = tokens[index + 1].content
        key = _normalize_heading(heading)
        occurrences[key] = occurrences.get(key, 0) + 1
        token.attrSet("id", context.heading_anchor(page_path, heading, occurrences[key]))


def _citation_labels(tokens) -> list[str]:
    labels: list[str] = []
    for token in tokens:
        if token.type == "citation":
            labels.append(str(token.meta["label"]))
        if token.children:
            labels.extend(_citation_labels(token.children))
    return labels


def _section_targets(
    *,
    pages: Iterable[WikiPage],
    sections: Iterable[WikiSection],
    route_base: str,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    page_by_id = {page.id: page for page in pages}
    headings_by_page = {
        page.id: _markdown_headings(page.body_markdown)
        for page in pages
    }
    grouped: dict[tuple[int, str], list[WikiSection]] = {}
    for section in sections:
        grouped.setdefault((section.page_id, _normalize_heading(section.heading)), []).append(section)

    anchors: dict[tuple[str, str], str] = {}
    hrefs: dict[str, str] = {}
    for (page_id, heading), matched_sections in grouped.items():
        page = page_by_id.get(page_id)
        if page is None or len(matched_sections) != 1 or headings_by_page.get(page_id, []).count(heading) != 1:
            continue
        section = matched_sections[0]
        anchor = f"section-{section.ordinal}"
        anchors[(page.path, heading)] = anchor
        hrefs[f"W:{section.page_slug}#{section.ordinal}"] = (
            f"{route_base.rstrip('/')}/{page.path.removeprefix('wiki/')}#{anchor}"
        )
    return hrefs, anchors


def _markdown_headings(markdown: str) -> list[str]:
    parser = MarkdownIt("commonmark", {"html": False})
    tokens = parser.parse(markdown)
    return [
        _normalize_heading(tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and index + 1 < len(tokens)
    ]


def _normalize_reference(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def _normalize_heading(value: str) -> str:
    return _normalize_reference(value)


def _stable_id(value: str) -> str:
    normalized = _normalize_heading(value).encode("utf-8")
    return hashlib.sha1(normalized).hexdigest()[:10]


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _is_safe_external_href(value: str) -> bool:
    return value.strip().lower().startswith(_SAFE_EXTERNAL_SCHEMES)


def _is_safe_href(value: str) -> bool:
    return value.startswith("/demo/wiki/") or _is_safe_external_href(value)
