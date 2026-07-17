"""FastAPI application factory."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings, get_settings
from domain_atlas.discovery.exa import ExaSearchProvider, SourceDiscoveryError
from domain_atlas.domain.artifacts import PAGE_TYPE_ORDER, KnowledgeArtifactRepository
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
from domain_atlas.workflow.background import BackgroundWorkflowRunner, WorkflowConflictError

templates = Jinja2Templates(directory="src/domain_atlas/web/templates")
static_files = StaticFiles(directory="src/domain_atlas/web/static")
templates.env.globals["static_version"] = lambda: str(
    max(
        int(Path("src/domain_atlas/web/static/styles.css").stat().st_mtime),
        int(Path("src/domain_atlas/web/static/app.js").stat().st_mtime),
    )
)


def create_app(
    settings: Settings | None = None,
    discovery_provider: ExaSearchProvider | None = None,
    chat_provider: object | None = None,
    embedding_provider: object | None = None,
    vector_index: VectorIndex | None = None,
    autopilot_runner: object | None = None,
    background_runner: object | None = None,
) -> FastAPI:
    """Create the Domain Atlas web app."""
    app_settings = settings or get_settings()
    initialize_database(app_settings.database_path)

    app = FastAPI(title=app_settings.app_name)
    app.state.settings = app_settings
    app.mount("/static", static_files, name="static")
    WorkflowRepository(app_settings.database_path).interrupt_active_runs()

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

    task_runner = background_runner or BackgroundWorkflowRunner(workflow_repository())

    def source_discovery_provider() -> ExaSearchProvider:
        return discovery_provider or ExaSearchProvider(api_key=app_settings.exa_api_key)

    def knowledge_build_workflow() -> KnowledgeBuildWorkflow:
        chat = chat_provider or OpenAICompatibleChatProvider(
            api_key=app_settings.llm_api_key,
            base_url=app_settings.llm_base_url,
            model=app_settings.chat_model,
            max_tokens=app_settings.chat_max_tokens,
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
            max_tokens=app_settings.chat_max_tokens,
        )
        return RetrievalQAService(
            database_path=app_settings.database_path,
            embedding_provider=embedder,
            vector_index=index,
            chat_provider=chat,
        )

    def autopilot_workflow() -> AutopilotWorkflow:
        if autopilot_runner is not None:
            return autopilot_runner
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
    def domain_dashboard(
        request: Request,
        project_id: int,
        error: str = "",
        notice: str = "",
    ) -> HTMLResponse:
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
                "workflow_labels": _workflow_labels(),
                "step_labels": _step_labels(),
                "active_workflow": any(run.status in {"queued", "running"} for run in workflow_runs),
                "error": error,
                "notice": notice,
            },
        )

    @app.get("/domains/{project_id}/workflow-status", response_class=HTMLResponse)
    def workflow_status(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        runs = workflow_repository().list_for_project(project_id, limit=3)
        return templates.TemplateResponse(
            request,
            "workflow_status.html",
            {
                "workflow_runs": runs,
                "workflow_labels": _workflow_labels(),
                "step_labels": _step_labels(),
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
            return _dashboard_redirect(project_id, error=f"搜索候选资料失败：{exc}")

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
            return _dashboard_redirect(project_id, error="确认候选资料失败：未找到该候选资料。")
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
            return _dashboard_redirect(project_id, error="上传失败：仅支持 Markdown 和 PDF 文件。")
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
            task_runner.submit(
                project_id=project_id,
                workflow_name="source_ingestion",
                work=lambda run_id: _run_source_ingestion(
                    source_ingestion_service(), workflow_repository(), source_id, run_id
                ),
            )
        except WorkflowConflictError as exc:
            return _dashboard_redirect(project_id, error=str(exc))
        return _dashboard_redirect(project_id, notice="已开始摄取资料，可在当前任务中查看进度。")

    @app.post("/domains/{project_id}/build")
    def build_knowledge(project_id: int) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            task_runner.submit(
                project_id=project_id,
                workflow_name="knowledge_build",
                work=lambda run_id: knowledge_build_workflow().run(project_id, run_id=run_id),
            )
        except WorkflowConflictError as exc:
            return _dashboard_redirect(project_id, error=str(exc))
        return _dashboard_redirect(project_id, notice="已开始构建知识库，可在当前任务中查看进度。")

    @app.post("/domains/{project_id}/autopilot")
    def run_autopilot(project_id: int) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            task_runner.submit(
                project_id=project_id,
                workflow_name="guided_autopilot",
                work=lambda run_id: _run_autopilot(autopilot_workflow(), project_id, run_id),
            )
        except WorkflowConflictError as exc:
            return _dashboard_redirect(project_id, error=str(exc))
        return _dashboard_redirect(project_id, notice="已开始一键构建领域地图，可在当前任务中查看进度。")

    @app.get("/domains/{project_id}/wiki", response_class=HTMLResponse)
    def wiki_pages(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        repository = artifact_repository()
        pages = repository.list_wiki_pages(project_id)
        groups = repository.list_wiki_page_groups(project_id)
        selected_page = repository.get_wiki_page_by_path(project_id, "wiki/index")
        if selected_page is None and pages:
            selected_page = pages[0]
        return templates.TemplateResponse(
            request,
            "wiki.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "pages": pages,
                "groups": groups,
                "selected_page": selected_page,
                "page_type_order": list(PAGE_TYPE_ORDER),
                "page_type_labels": _page_type_labels(),
            },
        )

    @app.get("/domains/{project_id}/wiki/{page_path:path}", response_class=HTMLResponse)
    def wiki_page_detail(request: Request, project_id: int, page_path: str) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        repository = artifact_repository()
        pages = repository.list_wiki_pages(project_id)
        groups = repository.list_wiki_page_groups(project_id)
        selected_page = repository.get_wiki_page_by_path(project_id, page_path)
        if selected_page is None:
            raise HTTPException(status_code=404, detail="Wiki page not found.")
        return templates.TemplateResponse(
            request,
            "wiki.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "pages": pages,
                "groups": groups,
                "selected_page": selected_page,
                "page_type_order": list(PAGE_TYPE_ORDER),
                "page_type_labels": _page_type_labels(),
            },
        )

    @app.get("/domains/{project_id}/path", response_class=HTMLResponse)
    def learning_path(request: Request, project_id: int) -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        repository = artifact_repository()
        guide = repository.get_learning_guide(project_id)
        modules = repository.list_learning_modules(project_id)
        pages = repository.list_wiki_pages(project_id)
        return templates.TemplateResponse(
            request,
            "learning_path.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "guide": guide,
                "modules": modules,
                "mainline_items": _learning_mainline_items(
                    guide=guide,
                    modules=modules,
                    pages=pages,
                    project_id=project_id,
                ),
                "guide_core_concepts": _guide_concept_items(
                    guide=guide,
                    pages=pages,
                    project_id=project_id,
                ),
            },
        )

    @app.get("/domains/{project_id}/qa", response_class=HTMLResponse)
    def qa_page(request: Request, project_id: int, error: str = "") -> HTMLResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        records = qa_repository().list_for_project(project_id)
        return templates.TemplateResponse(
            request,
            "qa.html",
            {
                "app_name": app_settings.app_name,
                "project": project,
                "records": records,
                "error": error,
            },
        )

    @app.post("/domains/{project_id}/qa")
    def ask_question(project_id: int, question: str = Form(...)) -> RedirectResponse:
        project = project_repository().get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Domain project not found.")
        try:
            retrieval_qa_service().answer(project_id=project_id, question=question)
        except Exception as exc:
            return RedirectResponse(
                url=f"/domains/{project_id}/qa?{urlencode({'error': f'回答失败：{exc}'})}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
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


def _dashboard_redirect(project_id: int, *, error: str = "", notice: str = "") -> RedirectResponse:
    query = {key: value for key, value in {"error": error, "notice": notice}.items() if value}
    suffix = f"?{urlencode(query)}" if query else ""
    return RedirectResponse(
        url=f"/domains/{project_id}{suffix}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _run_source_ingestion(
    service: IngestionService,
    repository: WorkflowRepository,
    source_id: int,
    run_id: int,
) -> None:
    def progress(step_name: str, step_status: str, output: dict[str, object] | None) -> None:
        repository.record_step(
            run_id,
            step_name=step_name,
            status=step_status,
            output=output,
            error=str((output or {}).get("error") or "") if step_status == "failed" else "",
        )

    service.ingest_source(source_id, progress=progress)
    repository.record_step(run_id, step_name="ingest", status="completed")


def _run_autopilot(workflow: object, project_id: int, run_id: int) -> object:
    """Keep deterministic legacy runners usable while production reuses the queued run."""
    try:
        return workflow.run(project_id, run_id=run_id)
    except TypeError as exc:
        if "run_id" not in str(exc):
            raise
        return workflow.run(project_id)


def _workflow_labels() -> dict[str, str]:
    return {
        "guided_autopilot": "一键构建领域地图",
        "knowledge_build": "构建知识库",
        "source_ingestion": "摄取资料",
    }


def _step_labels() -> dict[str, str]:
    return {
        "discover_candidates": "搜索候选资料",
        "select_candidates": "筛选资料",
        "ingest_sources": "摄取资料",
        "build_knowledge": "生成 Wiki 与课程",
        "compile_context": "整理上下文",
        "generate_artifacts": "生成结构化内容",
        "repair_lesson_structure": "修复课程结构",
        "persist_artifacts": "写入产物",
        "load": "抓取 / 读取",
        "parse": "解析与切分",
        "embed": "生成 Embedding",
        "index": "写入索引",
        "ingest": "完成摄取",
        "workflow": "任务执行",
        "interrupted": "任务中断",
        "knowledge_build": "构建知识库",
        "guided_autopilot": "一键构建领域地图",
    }


def _page_type_labels() -> dict[str, str]:
    return {
        "index": "index",
        "log": "log",
        "source": "sources",
        "concept": "concepts",
        "entity": "entities",
        "synthesis": "synthesis",
        "template": "templates",
        "query": "queries",
    }


def _learning_mainline_items(*, guide, modules, pages, project_id: int) -> list[dict[str, Any]]:
    """Prepare stable lesson and concept navigation without mutating persisted artifacts."""
    if guide is None:
        return []
    module_by_stage = {module.stage: module for module in modules}
    concept_urls = _concept_wiki_urls(pages, project_id)
    items: list[dict[str, Any]] = []
    for index, item in enumerate(guide.mainline):
        if not isinstance(item, dict):
            continue
        stage = _mainline_stage(item, modules, index)
        module = module_by_stage.get(stage)
        concept_names = _string_values(item.get("concept_names"))[:4]
        if not concept_names and module is not None:
            concept_names = [name for name in module.key_concepts if str(name).strip()][:4]
        items.append(
            {
                "title": str(item.get("title") or "主线节点"),
                "explanation": str(item.get("explanation") or ""),
                "learning_outcome": str(item.get("learning_outcome") or item.get("explanation") or ""),
                "module_stage": stage,
                "module_title": module.title if module is not None else "对应课程",
                "lesson_href": f"#lesson-stage-{stage}" if module is not None else "",
                "concepts": [
                    {"name": name, "href": concept_urls.get(name.casefold(), "")}
                    for name in concept_names
                ],
                "citations": _string_values(item.get("citations")),
            }
        )
    return items


def _guide_concept_items(*, guide, pages, project_id: int) -> list[dict[str, Any]]:
    if guide is None:
        return []
    concept_urls = _concept_wiki_urls(pages, project_id)
    items: list[dict[str, Any]] = []
    for concept in guide.core_concepts:
        if not isinstance(concept, dict):
            continue
        name = str(concept.get("name") or "概念")
        items.append(
            {
                **concept,
                "name": name,
                "wiki_href": concept_urls.get(name.casefold(), ""),
            }
        )
    return items


def _concept_wiki_urls(pages, project_id: int) -> dict[str, str]:
    return {
        page.title.casefold(): f"/domains/{project_id}/wiki/{page.path.removeprefix('wiki/')}"
        for page in pages
        if page.page_type == "concept" and page.title.strip()
    }


def _mainline_stage(item: dict[str, Any], modules, index: int) -> int:
    try:
        stage = int(item.get("module_stage") or item.get("stage") or 0)
    except (TypeError, ValueError):
        stage = 0
    available = {module.stage for module in modules}
    if stage in available:
        return stage
    if not modules:
        return 0
    return modules[min(index, len(modules) - 1)].stage


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
