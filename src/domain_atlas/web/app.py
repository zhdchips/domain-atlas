"""FastAPI application factory."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings, get_settings
from domain_atlas.discovery.exa import ExaSearchProvider, SourceDiscoveryError
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.qa import QARepository
from domain_atlas.domain.source_candidates import SourceCandidateRepository
from domain_atlas.domain.sources import ChunkRepository, CreateSource, SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.ingestion.service import IngestionService
from domain_atlas.providers.chat import OpenAICompatibleChatProvider
from domain_atlas.providers.embeddings import OpenAICompatibleEmbeddingProvider
from domain_atlas.providers.vector_index import ChromaVectorIndex, VectorIndex
from domain_atlas.qa.service import RetrievalQAService
from domain_atlas.workflow.build import KnowledgeBuildWorkflow
from domain_atlas.workflow.autopilot import AutopilotWorkflow

templates = Jinja2Templates(directory="src/domain_atlas/web/templates")
static_files = StaticFiles(directory="src/domain_atlas/web/static")


def create_app(
    settings: Settings | None = None,
    discovery_provider: ExaSearchProvider | None = None,
    chat_provider: object | None = None,
    embedding_provider: object | None = None,
    vector_index: VectorIndex | None = None,
) -> FastAPI:
    """Create the Domain Atlas web app."""
    app_settings = settings or get_settings()
    initialize_database(app_settings.database_path)

    app = FastAPI(title=app_settings.app_name)
    app.state.settings = app_settings
    app.mount("/static", static_files, name="static")

    def project_repository() -> DomainProjectRepository:
        return DomainProjectRepository(app_settings.database_path)

    def candidate_repository() -> SourceCandidateRepository:
        return SourceCandidateRepository(app_settings.database_path)

    def source_repository() -> SourceRepository:
        return SourceRepository(app_settings.database_path)

    def chunk_repository() -> ChunkRepository:
        return ChunkRepository(app_settings.database_path)

    def artifact_repository() -> KnowledgeArtifactRepository:
        return KnowledgeArtifactRepository(app_settings.database_path)

    def qa_repository() -> QARepository:
        return QARepository(app_settings.database_path)

    def workflow_repository() -> WorkflowRepository:
        return WorkflowRepository(app_settings.database_path)

    def source_discovery_provider() -> ExaSearchProvider:
        return discovery_provider or ExaSearchProvider(api_key=app_settings.exa_api_key)

    def knowledge_build_workflow() -> KnowledgeBuildWorkflow:
        chat = chat_provider or OpenAICompatibleChatProvider(
            api_key=app_settings.llm_api_key,
            base_url=app_settings.llm_base_url,
            model=app_settings.chat_model,
        )
        return KnowledgeBuildWorkflow(
            database_path=app_settings.database_path,
            chat_provider=chat,
            embedding_provider=embedding_provider
            or OpenAICompatibleEmbeddingProvider(
                api_key=app_settings.embedding_api_key,
                base_url=app_settings.embedding_base_url,
                model=app_settings.embedding_model,
                dimensions=app_settings.embedding_dimensions,
            ),
            vector_index=vector_index or ChromaVectorIndex(app_settings.chroma_path),
        )

    def source_ingestion_service() -> IngestionService:
        embedder = embedding_provider or OpenAICompatibleEmbeddingProvider(
            api_key=app_settings.embedding_api_key,
            base_url=app_settings.embedding_base_url,
            model=app_settings.embedding_model,
            dimensions=app_settings.embedding_dimensions,
        )
        index = vector_index or ChromaVectorIndex(app_settings.chroma_path)
        return IngestionService(
            database_path=app_settings.database_path,
            data_dir=app_settings.data_dir,
            embedding_provider=embedder,
            vector_index=index,
        )

    def retrieval_qa_service() -> RetrievalQAService:
        embedder = embedding_provider or OpenAICompatibleEmbeddingProvider(
            api_key=app_settings.embedding_api_key,
            base_url=app_settings.embedding_base_url,
            model=app_settings.embedding_model,
            dimensions=app_settings.embedding_dimensions,
        )
        index = vector_index or ChromaVectorIndex(app_settings.chroma_path)
        chat = chat_provider or OpenAICompatibleChatProvider(
            api_key=app_settings.llm_api_key,
            base_url=app_settings.llm_base_url,
            model=app_settings.chat_model,
        )
        return RetrievalQAService(
            database_path=app_settings.database_path,
            embedding_provider=embedder,
            vector_index=index,
            chat_provider=chat,
        )

    def autopilot_workflow() -> AutopilotWorkflow:
        return AutopilotWorkflow(
            database_path=app_settings.database_path,
            discovery_provider=source_discovery_provider(),
            ingestion_runner=source_ingestion_service(),
            build_runner=knowledge_build_workflow(),
            search_limit=app_settings.search_max_results,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": app_settings.app_name}

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        projects = project_repository().list_recent()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "app_name": app_settings.app_name,
                "projects": projects,
                "default_language": app_settings.default_language,
            },
        )

    @app.post("/domains")
    def create_domain(
        name: str = Form(...),
        goal: str = Form(""),
        level: str = Form("beginner"),
        language: str = Form("zh"),
        interaction_mode: str = Form("guided"),
    ) -> RedirectResponse:
        project = project_repository().create(
            CreateDomainProject(
                name=name,
                goal=goal,
                level=level,
                language=language,
                interaction_mode=interaction_mode,
            )
        )
        return RedirectResponse(
            url=f"/domains/{project.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.get("/domains/{project_id}", response_class=HTMLResponse)
    def domain_dashboard(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        candidates = candidate_repository().list_for_project(
            project_id,
            limit=app_settings.search_display_results,
        )
        sources = source_repository().list_for_project(project_id)
        chunk_count = chunk_repository().count_for_project(project_id)
        wiki_count = artifact_repository().count_wiki_pages(project_id)
        workflow_runs = workflow_repository().list_for_project(project_id, limit=3)

        return templates.TemplateResponse(
            request,
            "domain_dashboard.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "candidates": candidates,
                "sources": sources,
                "chunk_count": chunk_count,
                "wiki_count": wiki_count,
                "search_max_results": app_settings.search_max_results,
                "workflow_runs": workflow_runs,
            },
        )

    @app.post("/domains/{project_id}/discover")
    def discover_sources(
        project_id: int,
        query: str = Form(""),
    ) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")

        search_query = query.strip() or project.name
        try:
            drafts = source_discovery_provider().search(
                search_query,
                limit=app_settings.search_max_results,
            )
        except SourceDiscoveryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        candidate_repository().replace_discovered(project_id, drafts)
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/candidates/{candidate_id}/confirm")
    def confirm_source_candidate(
        project_id: int,
        candidate_id: int,
    ) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        candidate = candidate_repository().accept(project_id, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Source candidate not found.")
        source_repository().create(
            CreateSource(
                project_id=project_id,
                source_type="url",
                title=candidate.title,
                locator=candidate.url,
                metadata={
                    "candidate_id": candidate.id,
                    "provider": candidate.provider,
                    "authority_score": candidate.authority_score,
                    "authority_reason": candidate.authority_reason,
                },
            )
        )
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/sources/url")
    def add_url_source(
        project_id: int,
        url: str = Form(...),
        title: str = Form(""),
    ) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        source_repository().create(
            CreateSource(
                project_id=project_id,
                source_type="url",
                title=title.strip() or url,
                locator=url.strip(),
            )
        )
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/sources/file")
    async def add_file_source(project_id: int, file: UploadFile) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        filename = file.filename or "source"
        suffix = Path(filename).suffix.lower()
        source_type = _source_type_from_suffix(suffix)
        if source_type is None:
            raise HTTPException(status_code=400, detail="Only Markdown and PDF files are supported.")
        content = await file.read()
        digest = hashlib.sha256(content).hexdigest()
        source = source_repository().create(
            CreateSource(
                project_id=project_id,
                source_type=source_type,
                title=Path(filename).stem,
                locator=f"upload:{digest}:{filename}",
                metadata={"filename": filename},
            )
        )
        upload_dir = app_settings.uploads_path / str(project_id) / str(source.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        raw_path = upload_dir / filename
        raw_path.write_bytes(content)
        source_repository().update_raw_path(source.id, str(raw_path))
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/sources/{source_id}/ingest")
    def ingest_source(project_id: int, source_id: int) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        source = source_repository().get(source_id)
        if source is None or source.project_id != project_id:
            raise HTTPException(status_code=404, detail="Source not found.")
        try:
            source_ingestion_service().ingest_source(source_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/build")
    def build_knowledge(project_id: int) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            knowledge_build_workflow().run(project_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/domains/{project_id}/autopilot")
    def run_autopilot(project_id: int) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            autopilot_workflow().run(project_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.get("/domains/{project_id}/wiki", response_class=HTMLResponse)
    def wiki_pages(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        pages = artifact_repository().list_wiki_pages(project_id)
        return templates.TemplateResponse(
            request,
            "wiki.html",
            {"app_name": app_settings.app_name, "project": project, "pages": pages},
        )

    @app.get("/domains/{project_id}/path", response_class=HTMLResponse)
    def learning_path(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        modules = artifact_repository().list_learning_modules(project_id)
        return templates.TemplateResponse(
            request,
            "learning_path.html",
            {"app_name": app_settings.app_name, "project": project, "modules": modules},
        )

    @app.get("/domains/{project_id}/qa", response_class=HTMLResponse)
    def qa_page(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        records = qa_repository().list_for_project(project_id)
        return templates.TemplateResponse(
            request,
            "qa.html",
            {"app_name": app_settings.app_name, "project": project, "records": records},
        )

    @app.post("/domains/{project_id}/qa")
    def ask_question(project_id: int, question: str = Form(...)) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            retrieval_qa_service().answer(project_id=project_id, question=question)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            url=f"/domains/{project_id}/qa",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return app


def _source_type_from_suffix(suffix: str) -> str | None:
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    return None
