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
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateRepository
from domain_atlas.domain.sources import ChunkRepository, CreateSource, SourceRepository
from domain_atlas.ingestion.service import IngestionService
from domain_atlas.providers.embeddings import OpenAICompatibleEmbeddingProvider
from domain_atlas.providers.vector_index import ChromaVectorIndex, VectorIndex

templates = Jinja2Templates(directory="src/domain_atlas/web/templates")
static_files = StaticFiles(directory="src/domain_atlas/web/static")


def create_app(
    settings: Settings | None = None,
    discovery_provider: ExaSearchProvider | None = None,
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

    def source_discovery_provider() -> ExaSearchProvider:
        return discovery_provider or ExaSearchProvider(api_key=app_settings.exa_api_key)

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
    ) -> RedirectResponse:
        project = project_repository().create(
            CreateDomainProject(
                name=name,
                goal=goal,
                level=level,
                language=language,
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

        return templates.TemplateResponse(
            request,
            "domain_dashboard.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "candidates": candidates,
                "sources": sources,
                "chunk_count": chunk_count,
                "search_max_results": app_settings.search_max_results,
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

    return app


def _source_type_from_suffix(suffix: str) -> str | None:
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    return None
