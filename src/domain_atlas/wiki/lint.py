"""Basic health checks for the persistent LLM Wiki."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from domain_atlas.domain.artifacts import KnowledgeArtifactRepository


@dataclass(frozen=True)
class WikiLintIssue:
    code: str
    message: str
    severity: str
    target: str


class WikiLintService:
    """Detect structural problems in the compiled Wiki layer."""

    def __init__(self, database_path: Path) -> None:
        self.repository = KnowledgeArtifactRepository(database_path)

    def lint_project(self, project_id: int) -> list[WikiLintIssue]:
        pages = self.repository.list_wiki_pages(project_id)
        sections = self.repository.list_wiki_sections(project_id)
        links = self.repository.list_wiki_links(project_id)

        issues: list[WikiLintIssue] = []
        for section in sections:
            if not section.citations and not section.source_citation_labels:
                issues.append(
                    WikiLintIssue(
                        code="wiki.section.missing_citation",
                        message=f"Wiki section '{section.heading}' has no citation.",
                        severity="warning",
                        target=section.section_uid,
                    )
                )

        for field_name, values in {
            "slug": [page.slug for page in pages],
            "topic_path": [page.topic_path for page in pages],
        }.items():
            counts = Counter(values)
            for value, count in counts.items():
                if value and count > 1:
                    issues.append(
                        WikiLintIssue(
                            code=f"wiki.page.duplicate_{field_name}",
                            message=f"Wiki page {field_name} '{value}' appears {count} times.",
                            severity="error",
                            target=value,
                        )
                    )

        linked_targets = {link.target_page_slug for link in links}
        source_slugs = {link.source_page_slug for link in links}
        root_slug = pages[0].slug if pages else ""
        for page in pages:
            if page.slug == root_slug:
                continue
            has_inbound_link = page.slug in linked_targets
            has_outbound_link = page.slug in source_slugs
            if not has_inbound_link and not has_outbound_link:
                issues.append(
                    WikiLintIssue(
                        code="wiki.page.orphan",
                        message=f"Wiki page '{page.title}' has no backlinks or outgoing links.",
                        severity="info",
                        target=page.slug,
                    )
                )

        return issues
