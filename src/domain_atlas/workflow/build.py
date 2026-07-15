"""Knowledge build workflow."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import DomainProjectRepository
from domain_atlas.domain.sources import ChunkRepository, SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.providers.vector_index import VectorIndex


class ChatProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


REQUIRED_GUIDE_QUESTIONS = [
    "是什么",
    "为什么存在",
    "如何工作",
    "有哪些组成",
    "有哪些流派/类型/方法论分支",
    "代表人物/组织/关键贡献者",
    "经典案例",
    "最佳实践",
    "失败案例/常见误区",
    "未来趋势",
]


class KnowledgeBuildWorkflow:
    """Compile ingested chunks into structured Domain Atlas artifacts."""

    def __init__(
        self,
        *,
        database_path: Path,
        chat_provider: ChatProvider,
        embedding_provider: EmbeddingProvider | None = None,
        vector_index: VectorIndex | None = None,
    ) -> None:
        self.project_repository = DomainProjectRepository(database_path)
        self.source_repository = SourceRepository(database_path)
        self.chunk_repository = ChunkRepository(database_path)
        self.artifact_repository = KnowledgeArtifactRepository(database_path)
        self.workflow_repository = WorkflowRepository(database_path)
        self.chat_provider = chat_provider
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index

    def run(self, project_id: int) -> dict[str, Any]:
        project = self.project_repository.get(project_id)
        if project is None:
            raise ValueError("Domain project not found.")
        chunks = self.chunk_repository.list_for_project(project_id, limit=40)
        if not chunks:
            raise ValueError("Knowledge build requires at least one ingested chunk.")

        run_id = self.workflow_repository.start_run(project_id, "knowledge_build")
        self.project_repository.update_build_status(project_id, "running")
        try:
            context = _format_context(chunks)
            system_prompt = _system_prompt(project.language)
            user_prompt = _user_prompt(
                domain_name=project.name,
                goal=project.goal,
                level=project.level,
                context=context,
            )
            self.workflow_repository.record_step(
                run_id,
                step_name="compile_context",
                status="completed",
                output={"chunk_count": len(chunks)},
            )
            payload = self.chat_provider.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            _validate_payload(payload)
            sources = [
                self.source_repository.get(source_id)
                for source_id in sorted({chunk.source_id for chunk in chunks})
            ]
            payload = _with_workspace_pages(
                payload=payload,
                domain_name=project.name,
                chunks=chunks,
                sources=[source for source in sources if source is not None],
            )
            self.workflow_repository.record_step(
                run_id,
                step_name="generate_artifacts",
                status="completed",
                output={
                    "wiki_pages": len(payload.get("wiki_pages", [])),
                    "learning_modules": len(payload.get("learning_modules", [])),
                    "concepts": len(payload.get("concepts", [])),
                },
            )
            self.artifact_repository.replace_project_artifacts(project_id, payload)
            sections = self.artifact_repository.list_wiki_sections(project_id)
            if self.embedding_provider is not None and self.vector_index is not None and sections:
                embeddings = self.embedding_provider.embed_texts(
                    [section.body_markdown for section in sections]
                )
                self.vector_index.upsert_wiki_sections(
                    project_id=project_id,
                    sections=sections,
                    embeddings=embeddings,
                )
            self.workflow_repository.record_step(
                run_id,
                step_name="persist_artifacts",
                status="completed",
                output={"status": "saved", "wiki_sections": len(sections)},
            )
            self.workflow_repository.finish_run(run_id)
            self.project_repository.update_build_status(project_id, "completed")
            return payload
        except Exception as exc:
            self.workflow_repository.record_step(
                run_id,
                step_name="knowledge_build",
                status="failed",
                error=str(exc),
            )
            self.workflow_repository.fail_run(run_id, str(exc))
            self.project_repository.update_build_status(project_id, "failed")
            raise


def _system_prompt(language: str) -> str:
    return (
        "You are Domain Atlas, an agentic domain learning system. "
        "Compile cited source chunks into structured knowledge artifacts. "
        "Return strict JSON only. "
        "Use encyclopedia-style wiki prose, not tutorial prose. "
        f"Output language: {language or 'zh'}."
    )


def _user_prompt(*, domain_name: str, goal: str, level: str, context: str) -> str:
    return f"""
Domain: {domain_name}
Goal: {goal or "Build a reliable domain learning map."}
Learner level: {level}

Use the cited chunks below as the only evidence:
{context}

Return a JSON object with exactly these keys:
- source_profiles: array of objects with source_id, summary, authority_note, coverage_note, citations.
- concepts: 8 to 12 objects with name, definition, prerequisites, related, citations.
- concept_edges: focused array of objects with source, target, relation, citations.
- wiki_pages: at most 3 curated objects with title, topic_path, summary, body_markdown, citations.
  Do not create index, log, source, concept, or template pages; the system will create those deterministically.
  Use wiki_pages only for synthesis, entity, or query pages that add cross-source insight.
  Each wiki page should include page_type, path, stable slug, and sections array when possible.
  Use page_type values: entity, synthesis, query.
  Use paths like wiki/entities/name, wiki/synthesis/name, wiki/queries/name.
  Each section should include heading, body_markdown, citations, source_citation_labels, source_chunk_uids, and links.
  Use [[Wiki Links]] inside section bodies where useful.
- learning_guide: object with summary, question_answers, mainline, core_concepts, branches, details, citations.
  question_answers must answer exactly these ten questions, in order: {", ".join(REQUIRED_GUIDE_QUESTIONS)}.
  Each question answer object must include question, answer, citations. Answers must contain concrete domain knowledge from the chunks, not generic study advice.
  mainline: 5 to 8 objects with title, explanation, citations. Explain the main narrative a learner should follow.
  core_concepts: 8 to 12 objects with name, explanation, depends_on, citations. Use dependency-aware concepts.
  branches: 3 to 6 objects with name, description, when_to_study, citations.
  details: 3 to 6 objects with title, description, practice_or_example, citations.
- learning_modules: exactly five objects with stage, title, objectives, readings, key_concepts, check_questions, practice_task, citations.
  Modules should build from the learning_guide: start with mainline and core concepts, then branch into details.
Keep the response compact and valid JSON. Prefer concise arrays and short encyclopedia-style paragraphs.
""".strip()


def _format_context(chunks) -> str:
    lines: list[str] = []
    for chunk in chunks:
        source_title = chunk.metadata.get("source_title", "Unknown source")
        lines.append(
            f"[{chunk.citation_label}] source_id={chunk.source_id} title={source_title}\n{chunk.text}"
        )
    return "\n\n".join(lines)


def _validate_payload(payload: dict[str, Any]) -> None:
    required = {
        "source_profiles",
        "concepts",
        "concept_edges",
        "wiki_pages",
        "learning_guide",
        "learning_modules",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Knowledge build payload missing keys: {', '.join(missing)}")
    if len(payload.get("learning_modules") or []) != 5:
        raise ValueError("Knowledge build must return exactly five learning modules.")
    guide = payload.get("learning_guide")
    if not isinstance(guide, dict):
        raise ValueError("Knowledge build must return a learning guide object.")
    question_answers = guide.get("question_answers") or []
    if len(question_answers) != len(REQUIRED_GUIDE_QUESTIONS):
        raise ValueError("Knowledge build learning guide must answer exactly ten key questions.")
    questions = [str(item.get("question", "")) for item in question_answers if isinstance(item, dict)]
    if questions != REQUIRED_GUIDE_QUESTIONS:
        raise ValueError("Knowledge build learning guide key questions are missing or out of order.")


def _with_workspace_pages(
    *,
    payload: dict[str, Any],
    domain_name: str,
    chunks,
    sources,
) -> dict[str, Any]:
    workspace = deepcopy(payload)
    pages = [page for page in workspace.get("wiki_pages", []) if isinstance(page, dict)]
    normalized_pages = [_normalize_page(page) for page in pages]

    for page in _source_pages(workspace.get("source_profiles"), sources):
        _append_page_if_missing(normalized_pages, page)
    for page in _concept_pages(workspace.get("concepts")):
        _append_page_if_missing(normalized_pages, page)
    _append_page_if_missing(normalized_pages, _synthesis_page(domain_name, normalized_pages))
    _append_page_if_missing(normalized_pages, _template_page("source"))
    _append_page_if_missing(normalized_pages, _template_page("concept"))

    index_page = _index_page(domain_name, normalized_pages)
    log_page = _log_page(
        domain_name=domain_name,
        source_count=len(sources),
        chunk_count=len(chunks),
        page_count=len(normalized_pages) + 2,
    )
    normalized_pages = [
        page
        for page in normalized_pages
        if page.get("path") not in {"wiki/index", "wiki/log"}
    ]
    workspace["wiki_pages"] = [index_page, log_page, *normalized_pages]
    return workspace


def _normalize_page(page: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(page)
    title = _str(normalized.get("title")) or "Untitled"
    page_type = _page_type(normalized)
    slug = _slug(normalized.get("slug") or title)
    normalized["title"] = title
    normalized["slug"] = slug
    normalized["page_type"] = page_type
    normalized["path"] = _page_path(normalized, page_type=page_type, slug=slug)
    normalized["topic_path"] = _str(normalized.get("topic_path")) or normalized["path"]
    normalized["summary"] = _str(normalized.get("summary"))
    normalized["body_markdown"] = _str(normalized.get("body_markdown"))
    normalized["citations"] = _string_list(normalized.get("citations"))
    return normalized


def _source_pages(source_profiles, sources) -> list[dict[str, Any]]:
    source_by_id = {source.id: source for source in sources}
    pages: list[dict[str, Any]] = []
    for profile in source_profiles if isinstance(source_profiles, list) else []:
        if not isinstance(profile, dict):
            continue
        source_id = int(profile.get("source_id") or 0)
        source = source_by_id.get(source_id)
        title = source.title if source else f"Source {source_id}"
        slug = _slug(f"source-{source_id}-{title or 'untitled'}")
        citations = _string_list(profile.get("citations"))
        pages.append(
            {
                "title": title,
                "slug": slug,
                "page_type": "source",
                "path": f"wiki/sources/{slug}",
                "topic_path": f"sources/{title}",
                "summary": _str(profile.get("summary")),
                "body_markdown": (
                    f"# {title}\n\n"
                    f"{_str(profile.get('summary'))}\n\n"
                    f"## Authority\n{_str(profile.get('authority_note'))}\n\n"
                    f"## Coverage\n{_str(profile.get('coverage_note'))}"
                ).strip(),
                "citations": citations,
                "sections": [
                    {
                        "section_uid": f"{slug}#source",
                        "heading": "Source summary",
                        "body_markdown": _str(profile.get("summary")),
                        "citations": citations,
                        "source_citation_labels": citations,
                    }
                ],
            }
        )
    return pages


def _concept_pages(concepts) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for concept in concepts if isinstance(concepts, list) else []:
        if not isinstance(concept, dict):
            continue
        name = _str(concept.get("name"))
        if not name:
            continue
        slug = _slug(name)
        citations = _string_list(concept.get("citations"))
        related = _string_list(concept.get("related"))
        prerequisites = _string_list(concept.get("prerequisites"))
        pages.append(
            {
                "title": name,
                "slug": slug,
                "page_type": "concept",
                "path": f"wiki/concepts/{slug}",
                "topic_path": f"concepts/{name}",
                "summary": _str(concept.get("definition")),
                "body_markdown": (
                    f"# {name}\n\n"
                    f"{_str(concept.get('definition'))}\n\n"
                    f"## Prerequisites\n{_bullets(prerequisites)}\n\n"
                    f"## Related\n{_bullets(related)}"
                ).strip(),
                "citations": citations,
                "sections": [
                    {
                        "section_uid": f"{slug}#definition",
                        "heading": "Definition",
                        "body_markdown": _str(concept.get("definition")),
                        "citations": citations,
                        "source_citation_labels": citations,
                    }
                ],
            }
        )
    return pages


def _synthesis_page(domain_name: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    source_summaries = [
        f"- [[{page['title']}]] - {page.get('summary', '')}"
        for page in pages
        if page.get("page_type") in {"source", "concept"}
    ][:12]
    body = (
        f"# {domain_name} 综合页\n\n"
        "本页汇总当前 Wiki 工作区中的资料页和概念页，用于快速把握领域主干。\n\n"
        + "\n".join(source_summaries)
    ).strip()
    return {
        "title": f"{domain_name} 综合页",
        "slug": "overview",
        "page_type": "synthesis",
        "path": "wiki/synthesis/overview",
        "topic_path": "synthesis/overview",
        "summary": f"{domain_name} 的跨资料综合索引。",
        "body_markdown": body,
        "citations": [],
        "sections": [
            {
                "section_uid": "synthesis-overview#1",
                "heading": "Overview",
                "body_markdown": body,
                "citations": [],
            }
        ],
    }


def _template_page(template_type: str) -> dict[str, Any]:
    label = {"source": "资料页", "concept": "概念页"}.get(template_type, template_type)
    title = f"{label}模板"
    slug = f"{template_type}-template"
    body = (
        f"# {title}\n\n"
        "## 用途\n说明该类型页面应该沉淀哪些信息。\n\n"
        "## 必要属性\n- title\n- page_type\n- path\n- citations\n\n"
        "## 正文要求\n使用简洁、百科式、带引用的 Wiki 文字。"
    )
    return {
        "title": title,
        "slug": slug,
        "page_type": "template",
        "path": f"wiki/templates/{template_type}",
        "topic_path": f"templates/{template_type}",
        "summary": f"{label}的结构模板。",
        "body_markdown": body,
        "citations": [],
        "sections": [
            {
                "section_uid": f"template-{template_type}#1",
                "heading": "Template",
                "body_markdown": body,
                "citations": [],
            }
        ],
    }


def _index_page(domain_name: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {
        "source": "资料摘要",
        "concept": "概念条目",
        "entity": "实体条目",
        "synthesis": "综合页",
        "template": "模板",
        "query": "查询页",
    }
    lines = [f"# {domain_name} Wiki 索引", "", "本页是 Wiki 工作区入口。先读这里，再进入具体页面。"]
    for page_type in ("source", "concept", "entity", "synthesis", "template", "query"):
        typed = [page for page in pages if page.get("page_type") == page_type]
        lines.extend(["", f"## {labels.get(page_type, page_type)}", ""])
        if not typed:
            lines.append("- 暂无页面。")
        for page in sorted(typed, key=lambda item: item.get("path", "")):
            lines.append(
                f"- [[{page.get('title', '未命名页面')}]] - {page.get('summary', '')} (`{page.get('path', '')}`)"
            )
    body = "\n".join(lines).strip()
    return {
        "title": "Wiki Index",
        "slug": "index",
        "page_type": "index",
        "path": "wiki/index",
        "topic_path": "index",
        "summary": "Wiki 工作区的中心目录。",
        "body_markdown": body,
        "citations": [],
        "sections": [
            {
                "section_uid": "index#1",
                "heading": "Wiki Index",
                "body_markdown": body,
                "citations": [],
            }
        ],
    }


def _log_page(*, domain_name: str, source_count: int, chunk_count: int, page_count: int) -> dict[str, Any]:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    body = (
        f"# Wiki 日志\n\n"
        f"## [{timestamp}] 构建 | {domain_name}\n\n"
        f"- 资料数: {source_count}\n"
        f"- 切片数: {chunk_count}\n"
        f"- Wiki 页面数: {page_count}\n"
        "- 动作: 生成工作区页面，刷新索引，并保留 provenance。"
    )
    return {
        "title": "Wiki Log",
        "slug": "log",
        "page_type": "log",
        "path": "wiki/log",
        "topic_path": "log",
        "summary": "Wiki 工作区的构建与维护日志。",
        "body_markdown": body,
        "citations": [],
        "sections": [
            {
                "section_uid": "log#1",
                "heading": "Build log",
                "body_markdown": body,
                "citations": [],
            }
        ],
    }


def _append_page_if_missing(pages: list[dict[str, Any]], page: dict[str, Any]) -> None:
    paths = {item.get("path") for item in pages}
    if page.get("path") not in paths:
        pages.append(_normalize_page(page))


def _page_type(page: dict[str, Any]) -> str:
    raw = _str(page.get("page_type") or page.get("type")).lower()
    if raw in {"index", "log", "source", "concept", "entity", "synthesis", "template", "query"}:
        return raw
    path = _str(page.get("path")).lower()
    if path.startswith("wiki/sources/"):
        return "source"
    if path.startswith("wiki/entities/"):
        return "entity"
    if path.startswith("wiki/synthesis/"):
        return "synthesis"
    if path.startswith("wiki/templates/"):
        return "template"
    if path == "wiki/index":
        return "index"
    if path == "wiki/log":
        return "log"
    return "concept"


def _page_path(page: dict[str, Any], *, page_type: str, slug: str) -> str:
    path = _str(page.get("path")).strip("/")
    if path:
        return path if path.startswith("wiki/") else f"wiki/{path}"
    if page_type in {"index", "log"}:
        return f"wiki/{page_type}"
    folder = {
        "source": "sources",
        "concept": "concepts",
        "entity": "entities",
        "synthesis": "synthesis",
        "template": "templates",
        "query": "queries",
    }.get(page_type, "concepts")
    return f"wiki/{folder}/{slug}"


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None yet."


def _slug(value: Any) -> str:
    text = _str(value).lower()
    text = re.sub(r"\[\[|\]\]", "", text)
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", text)
    return text.strip("-") or "untitled"
