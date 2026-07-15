"""Knowledge build workflow."""

from __future__ import annotations

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
- concepts: array of objects with name, definition, prerequisites, related, citations.
- concept_edges: array of objects with source, target, relation, citations.
- wiki_pages: array of objects with title, topic_path, summary, body_markdown, citations.
  Each wiki page should include a stable slug and sections array when possible.
  Each section should include heading, body_markdown, citations, source_citation_labels, source_chunk_uids, and links.
  Use [[Wiki Links]] inside section bodies where useful.
- learning_modules: exactly five objects with stage, title, objectives, readings, key_concepts, check_questions, practice_task, citations.
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
        "learning_modules",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Knowledge build payload missing keys: {', '.join(missing)}")
    if len(payload.get("learning_modules") or []) != 5:
        raise ValueError("Knowledge build must return exactly five learning modules.")
