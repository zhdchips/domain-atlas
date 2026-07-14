"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings, get_settings
from domain_atlas.discovery.exa import ExaSearchProvider, SourceDiscoveryError
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateRepository

templates = Jinja2Templates(directory="src/domain_atlas/web/templates")
static_files = StaticFiles(directory="src/domain_atlas/web/static")


def create_app(
    settings: Settings | None = None,
    discovery_provider: ExaSearchProvider | None = None,
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

    def source_discovery_provider() -> ExaSearchProvider:
        return discovery_provider or ExaSearchProvider(api_key=app_settings.exa_api_key)

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

        return templates.TemplateResponse(
            request,
            "domain_dashboard.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "candidates": candidates,
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
        return RedirectResponse(
            url=f"/domains/{project_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return app
