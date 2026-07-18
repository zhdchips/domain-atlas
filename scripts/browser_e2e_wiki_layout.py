"""Run Playwright checks for the Wiki workspace layout."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.intake.assessment import IntakeAssessment


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("FAIL browser-e2e: playwright is not installed.")
        print("Run: uv sync --extra dev && uv run python -m playwright install chromium")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="domain-atlas-browser-e2e-"))
    server: subprocess.Popen[str] | None = None
    try:
        data_dir = workdir / "data"
        settings = Settings(data_dir=data_dir)
        (
            project_id,
            llm_intake_project_id,
            mobile_intake_project_id,
            exhaustion_project_id,
        ) = _create_wiki_fixture(settings)
        port = _free_port()
        server = _start_server(data_dir=data_dir, port=port)
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base_url}/domains/{project_id}/wiki/index", wait_until="networkidle")
            page.locator(".wiki-workspace").wait_for(state="visible", timeout=5000)
            _assert_wiki_layout(page)
            page.goto(f"{base_url}/domains/{project_id}/path", wait_until="networkidle")
            page.locator(".qa-grid").wait_for(state="visible", timeout=5000)
            _assert_learning_guide_layout(page)
            _assert_learning_navigation(page, base_url=base_url, project_id=project_id)
            page.goto(f"{base_url}/domains/{project_id}", wait_until="networkidle")
            _assert_dashboard_task_feedback(page)
            _assert_guided_autopilot_flow(page)
            page.goto(f"{base_url}/domains/{exhaustion_project_id}", wait_until="networkidle")
            _assert_guided_exhaustion_feedback(page)
            page.goto(f"{base_url}/domains/{llm_intake_project_id}/intake", wait_until="networkidle")
            _assert_llm_enhanced_intake(page)
            page.goto(f"{base_url}/", wait_until="networkidle")
            _assert_clear_project_intake(page)
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{base_url}/domains/{mobile_intake_project_id}/intake", wait_until="networkidle")
            _assert_mobile_project_intake(page)
            _assert_mobile_no_horizontal_overflow(page)
            browser.close()
    except PlaywrightError as exc:
        print(f"FAIL browser-e2e: Playwright could not run Chromium: {exc}")
        print("Run: uv run python -m playwright install chromium")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    except Exception as exc:
        print(f"FAIL browser-e2e: {exc}")
        print(f"workdir preserved for inspection: {workdir}")
        return 1
    finally:
        if server is not None:
            _stop_server(server)

    shutil.rmtree(workdir, ignore_errors=True)
    print("PASS browser-e2e wiki and learning guide layout")
    return 0


def _create_wiki_fixture(settings: Settings) -> tuple[int, int, int, int]:
    initialize_database(settings.database_path)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(
            name="Browser Layout Regression",
            goal="Validate Wiki workspace rendering.",
            language="zh",
        )
    )
    KnowledgeArtifactRepository(settings.database_path).replace_project_artifacts(
        project.id,
        {
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_guide": _learning_guide_payload(),
            "learning_modules": [
                {
                    "stage": stage,
                    "title": title,
                    "stage_overview": f"{title}阶段说明 Domain Atlas 如何把资料转为可学习内容。",
                    "core_explanation": "学习主体由 Agent 从证据中提取和组织，citation 与 provenance 用于回到来源核验。[S1-C1]",
                    "knowledge_blocks": [
                        {
                            "title": "Agent 讲解优先",
                            "body": "页面先展示可直接学习的讲解，再展示可选证据来源。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                        {
                            "title": "课程组织",
                            "body": "主线将学习目标连接到章节，章节再把机制、案例和练习组织成连续学习过程。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                        {
                            "title": "证据边界",
                            "body": "来源用于核验讲解中的主张和延伸阅读，不能替代面向学习者的课程正文。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                    ],
                    "examples": [
                        {
                            "title": "Wiki 到课程章节",
                            "body": "WikiSection 可作为证据，学习模块负责把证据组织成课程章节。[S1-C1]",
                            "citations": ["S1-C1"],
                        }
                    ],
                    "misconceptions": [
                        {
                            "title": "把来源列表当课程",
                            "correction": "来源列表只用于溯源和深入阅读，不是默认学习主体。[S1-C1]",
                            "citations": ["S1-C1"],
                        }
                    ],
                    "objectives": ["理解领域主线", "区分课程与证据来源"],
                    "readings": ["Wiki Index [S1-C1]"],
                    "key_concepts": ["Provenance", "WikiSection"],
                    "check_questions": ["为什么需要 provenance？", "为什么来源不是课程主体？"],
                    "practice_task": "用一段话说明 citation 和 provenance 的关系。",
                    "further_reading": [
                        {"title": "Wiki Index", "locator": "wiki/index", "citations": ["S1-C1"]}
                    ],
                    "citations": ["S1-C1"],
                }
                for stage, title in enumerate(
                    ["入门认知", "核心概念", "关键方法", "实践应用", "进阶专题"],
                    start=1,
                )
            ],
            "wiki_pages": [
                _page("index", "wiki/index", "Wiki Index", "Wiki 工作区的中心目录。"),
                _page("log", "wiki/log", "Wiki Log", "Wiki 工作区的构建日志。"),
                _page(
                    "source",
                    "wiki/sources/domain-atlas-source",
                    "Domain Atlas Source",
                    "固定资料摘要。",
                ),
                _page("concept", "wiki/concepts/provenance", "Provenance", "可溯源能力。"),
                _page("concept", "wiki/concepts/wiki-section", "WikiSection", "可检索段落。"),
                _page("entity", "wiki/entities/domain-atlas", "Domain Atlas", "领域学习系统。"),
                _page("synthesis", "wiki/synthesis/overview", "综合页", "跨页面综合。"),
                _page("template", "wiki/templates/source", "资料页模板", "资料页结构模板。"),
                _page("template", "wiki/templates/concept", "概念页模板", "概念页结构模板。"),
            ],
        },
    )
    workflow_repository = WorkflowRepository(settings.database_path)
    run_id = workflow_repository.start_run(project.id, "knowledge_build")
    workflow_repository.record_step(
        run_id, step_name="compile_context", status="completed", output={"chunk_count": 1}
    )
    workflow_repository.finish_run(run_id)
    llm_project = _create_llm_intake_fixture(settings, name="Agent")
    mobile_llm_project = _create_llm_intake_fixture(settings, name="数据治理")
    exhausted_project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(name="旅行代理", scope="旅行代理", interaction_mode="guided")
    )
    exhausted_run_id = workflow_repository.start_run(exhausted_project.id, "guided_autopilot")
    recovery_message = (
        "候选资料已尝试完毕，仅成功摄取 0/2 份。失败原因包括：访问受限。"
        "可稍后重试，或手动添加可访问的 URL、Markdown/PDF，也可调整领域范围后重新搜索。"
    )
    workflow_repository.record_step(
        exhausted_run_id,
        step_name="ingest_sources",
        status="failed",
        output={
            "completed": 0,
            "total": 2,
            "success_count": 0,
            "attempted_count": 2,
            "failed_count": 2,
            "minimum_build_sources": 2,
            "terminal_reason": "candidates_exhausted",
            "recovery_message": recovery_message,
        },
    )
    workflow_repository.fail_run(exhausted_run_id, recovery_message)
    return project.id, llm_project.id, mobile_llm_project.id, exhausted_project.id


def _create_llm_intake_fixture(settings: Settings, *, name: str):
    assessment = IntakeAssessment(
        needs_clarification=True,
        reason="领域覆盖多个常见学习切入面。",
        understanding=f"“{name}”需要先确认适合你的学习切入面。",
        question=f"你希望先从{name}的哪个切入面学习？",
        options=[
            {
                "value": "foundations",
                "label": "方法基础",
                "description": "理解核心概念、方法论与关键流程。",
                "scope": f"{name} 方法基础",
            },
            {
                "value": "practice",
                "label": "落地实践",
                "description": "围绕案例、组织落地和实践方法学习。",
                "scope": f"{name} 落地实践",
            },
        ],
        default_scope=f"{name} 方法基础",
        assumptions=["确认后会以选择的范围组织资料和课程。"],
        confidence=0.87,
        recommended_option="foundations",
    )
    return DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(
            name=name,
            goal="学习",
            scope=assessment.default_scope,
            intake_status="needs_clarification",
            intake_metadata={
                **assessment.to_metadata(),
                "assessment_source": "llm",
                "assessment_status": "applied",
            },
        )
    )


def _learning_guide_payload() -> dict[str, Any]:
    questions = [
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
    return {
        "summary": "Domain Atlas 是用于生成可溯源领域 Wiki 和学习导览的系统。[S1-C1]",
        "question_answers": [
            {
                "question": question,
                "answer": f"{question}：学习者应围绕资料摄取、Wiki 结构、citation 和 provenance 建立知识地图。[S1-C1]",
                "citations": ["S1-C1"],
            }
            for question in questions
        ],
        "mainline": [
            {
                "title": f"阶段 {stage}：从资料到课程",
                "explanation": "先摄取权威资料，再生成 Wiki 页面、段落和引用证据。[S1-C1]",
                "learning_outcome": "能从主线进入对应课程，并区分课程正文和证据来源。",
                "module_stage": stage,
                "concept_names": ["Provenance", "WikiSection"],
                "citations": ["S1-C1"],
            }
            for stage in range(1, 6)
        ],
        "core_concepts": [
            {
                "name": "Provenance",
                "explanation": "记录答案和页面内容可追溯到哪些证据。[S1-C1]",
                "depends_on": ["Citation"],
                "citations": ["S1-C1"],
            },
            {
                "name": "WikiSection",
                "explanation": "可检索、可嵌入、可引用的 Wiki 段落。[S1-C1]",
                "depends_on": ["Wiki Page"],
                "citations": ["S1-C1"],
            },
        ],
        "branches": [
            {
                "name": "检索问答",
                "description": "围绕 WikiSection 和 citation 生成可溯源答案。[S1-C1]",
                "when_to_study": "理解 Wiki 工作区后。",
                "citations": ["S1-C1"],
            }
        ],
        "details": [
            {
                "title": "引用完整性",
                "description": "检查页面和答案是否保留证据标签。[S1-C1]",
                "practice_or_example": "验证一个回答至少包含一个 Wiki citation。",
                "citations": ["S1-C1"],
            }
        ],
        "citations": ["S1-C1"],
    }


def _page(page_type: str, path: str, title: str, summary: str) -> dict[str, Any]:
    slug = path.rstrip("/").split("/")[-1]
    return {
        "slug": slug,
        "page_type": page_type,
        "path": path,
        "title": title,
        "topic_path": path.removeprefix("wiki/"),
        "summary": summary,
        "body_markdown": f"# {title}\n\n{summary}\n\n- [[Provenance]]\n- [[WikiSection]]",
        "citations": ["S1-C1"] if page_type in {"source", "concept", "entity", "synthesis"} else [],
        "sections": [
            {
                "section_uid": f"{slug}#1",
                "heading": title,
                "body_markdown": summary,
                "citations": [f"W:{slug}#1"],
                "source_citation_labels": ["S1-C1"],
                "source_chunk_uids": ["chunk:layout:1"],
                "links": ["Provenance", "WikiSection"],
            }
        ],
    }


def _start_server(*, data_dir: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["INTAKE_LLM_ASSESSMENT_ENABLED"] = "false"
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.browser_e2e_fixture_app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + 20
    with httpx.Client(timeout=1.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
    raise RuntimeError("server did not become healthy")


def _assert_wiki_layout(page) -> None:
    metrics = page.evaluate(
        """
        () => {
          const workspace = document.querySelector(".wiki-workspace");
          const tree = document.querySelector(".wiki-tree");
          const article = document.querySelector(".wiki-page");
          const stylesheet = document.querySelector('link[href*="styles.css?v="]');
          const treeBox = tree.getBoundingClientRect();
          const articleBox = article.getBoundingClientRect();
          return {
            stylesheetHref: stylesheet ? stylesheet.href : "",
            workspaceDisplay: getComputedStyle(workspace).display,
            workspaceColumns: getComputedStyle(workspace).gridTemplateColumns,
            treeX: treeBox.x,
            treeWidth: treeBox.width,
            articleX: articleBox.x,
            articleWidth: articleBox.width,
            articleTop: articleBox.y,
            linkCount: document.querySelectorAll(".wiki-tree-link").length,
            activeText: document.querySelector(".wiki-tree-link.active")?.textContent || "",
          };
        }
        """
    )
    failures: list[str] = []
    if "styles.css?v=" not in metrics["stylesheetHref"]:
        failures.append("stylesheet version parameter is missing")
    if metrics["workspaceDisplay"] != "grid":
        failures.append(f"workspace display is {metrics['workspaceDisplay']!r}, expected 'grid'")
    if metrics["treeWidth"] < 280:
        failures.append(f"wiki tree width is too small: {metrics['treeWidth']:.1f}")
    if metrics["articleWidth"] < 600:
        failures.append(f"wiki article width is too small: {metrics['articleWidth']:.1f}")
    if metrics["articleX"] <= metrics["treeX"] + metrics["treeWidth"] + 12:
        failures.append(
            "wiki article is not laid out to the right of the tree: "
            f"treeX={metrics['treeX']:.1f} treeWidth={metrics['treeWidth']:.1f} "
            f"articleX={metrics['articleX']:.1f}"
        )
    if metrics["linkCount"] < 8:
        failures.append(f"expected at least 8 tree links, got {metrics['linkCount']}")
    if "Wiki Index" not in metrics["activeText"]:
        failures.append(f"active tree link did not select Wiki Index: {metrics['activeText']!r}")
    if failures:
        raise RuntimeError("; ".join(failures))
    print(
        "verified wiki layout "
        f"columns={metrics['workspaceColumns']} "
        f"tree={metrics['treeWidth']:.0f}px article={metrics['articleWidth']:.0f}px"
    )


def _assert_learning_guide_layout(page) -> None:
    metrics = page.evaluate(
        """
        () => {
          const qaGrid = document.querySelector(".qa-grid");
          const columns = document.querySelector(".learning-columns");
          const firstCard = document.querySelector(".qa-card");
          const hero = document.querySelector(".learning-guide-hero");
          const qaBox = qaGrid.getBoundingClientRect();
          const columnsBox = columns.getBoundingClientRect();
          const blockGrid = document.querySelector(".lesson-block-grid");
          const evidence = document.querySelector(".evidence-reading");
          const mainlineLinks = document.querySelectorAll(".lesson-link");
          return {
            text: document.body.innerText,
            qaDisplay: getComputedStyle(qaGrid).display,
            qaColumns: getComputedStyle(qaGrid).gridTemplateColumns,
            columnsDisplay: getComputedStyle(columns).display,
            columnsTemplate: getComputedStyle(columns).gridTemplateColumns,
            blockGridDisplay: getComputedStyle(blockGrid).display,
            blockGridColumns: getComputedStyle(blockGrid).gridTemplateColumns,
            qaCount: document.querySelectorAll(".qa-card").length,
            moduleCount: document.querySelectorAll(".learning-module").length,
            lessonBlockCount: document.querySelectorAll(".lesson-block").length,
            mainlineLinkCount: mainlineLinks.length,
            lessonTargetCount: document.querySelectorAll(".learning-module[id^='lesson-stage-']").length,
            conceptLinkCount: document.querySelectorAll(".mainline-concepts a").length,
            evidenceHeading: evidence.querySelector("h3")?.textContent || "",
            firstCardHeight: firstCard.getBoundingClientRect().height,
            heroWidth: hero.getBoundingClientRect().width,
            qaWidth: qaBox.width,
            columnsWidth: columnsBox.width,
          };
        }
        """
    )
    failures: list[str] = []
    if "领域速览" not in metrics["text"] or "关键问题" not in metrics["text"]:
        failures.append("learning guide semantic headings are missing")
    if "未来趋势" not in metrics["text"]:
        failures.append("ten-question guide does not include future trends")
    if metrics["qaDisplay"] != "grid":
        failures.append(f"qa grid display is {metrics['qaDisplay']!r}, expected 'grid'")
    if metrics["columnsDisplay"] != "grid":
        failures.append(f"learning columns display is {metrics['columnsDisplay']!r}, expected 'grid'")
    if metrics["blockGridDisplay"] != "grid":
        failures.append(f"lesson block grid display is {metrics['blockGridDisplay']!r}, expected 'grid'")
    if metrics["qaCount"] != 10:
        failures.append(f"expected 10 question cards, got {metrics['qaCount']}")
    if metrics["moduleCount"] != 5:
        failures.append(f"expected 5 learning modules, got {metrics['moduleCount']}")
    if metrics["lessonBlockCount"] < 5:
        failures.append(f"expected lesson blocks for modules, got {metrics['lessonBlockCount']}")
    if metrics["evidenceHeading"] != "证据来源 / 深入阅读":
        failures.append(f"evidence heading is {metrics['evidenceHeading']!r}")
    if "阅读材料" in metrics["text"]:
        failures.append("legacy reading-material heading is still visible")
    if metrics["firstCardHeight"] < 80:
        failures.append(f"first question card is too short: {metrics['firstCardHeight']:.1f}")
    if metrics["heroWidth"] < 700 or metrics["qaWidth"] < 700 or metrics["columnsWidth"] < 700:
        failures.append(
            "learning guide content is unexpectedly narrow: "
            f"hero={metrics['heroWidth']:.1f} qa={metrics['qaWidth']:.1f} "
            f"columns={metrics['columnsWidth']:.1f}"
        )
    if metrics["mainlineLinkCount"] != 5 or metrics["lessonTargetCount"] != 5:
        failures.append(
            "mainline navigation does not map every stage: "
            f"links={metrics['mainlineLinkCount']} targets={metrics['lessonTargetCount']}"
        )
    if metrics["conceptLinkCount"] < 1:
        failures.append("mainline does not expose a Wiki concept link")
    if failures:
        raise RuntimeError("; ".join(failures))
    print(
        "verified learning guide layout "
        f"qa_columns={metrics['qaColumns']} "
        f"content_columns={metrics['columnsTemplate']} "
        f"lesson_columns={metrics['blockGridColumns']}"
    )


def _assert_learning_navigation(page, *, base_url: str, project_id: int) -> None:
    page.locator(".lesson-link").first.click()
    target = page.locator("#lesson-stage-1")
    target.wait_for(state="visible", timeout=5000)
    target_box = target.bounding_box()
    if target_box is None or target_box["y"] > 180:
        raise RuntimeError(f"lesson anchor did not bring stage 1 into view: {target_box}")

    page.goto(f"{base_url}/domains/{project_id}/path", wait_until="networkidle")
    page.locator(".mainline-concepts a").first.click()
    page.locator(".wiki-page").wait_for(state="visible", timeout=5000)
    if not page.url.endswith(f"/domains/{project_id}/wiki/concepts/provenance"):
        raise RuntimeError(f"mainline concept link opened unexpected URL: {page.url}")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base_url}/domains/{project_id}/path", wait_until="networkidle")
    mobile = page.evaluate(
        """
        () => ({
          viewport: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          mainlineWidth: document.querySelector('.mainline-navigation').getBoundingClientRect().width,
          lessonLinkWidth: document.querySelector('.lesson-link').getBoundingClientRect().width,
        })
        """
    )
    if mobile["documentWidth"] > mobile["viewport"] + 1:
        raise RuntimeError(f"mobile learning page overflows horizontally: {mobile}")
    if mobile["lessonLinkWidth"] > mobile["mainlineWidth"]:
        raise RuntimeError(f"mobile lesson link overflows mainline item: {mobile}")
    print("verified mainline navigation, Wiki concept link, and mobile layout")


def _assert_dashboard_task_feedback(page) -> None:
    if "当前任务" not in page.locator("body").inner_text():
        raise RuntimeError("dashboard current-task area is missing")
    if "整理上下文" not in page.locator("body").inner_text():
        raise RuntimeError("dashboard does not render persisted workflow steps")

    form = page.locator("form[action$='/build']")
    form.evaluate("form => form.addEventListener('submit', event => event.preventDefault(), { once: true })")
    form.locator("button").click()
    button = form.locator("button")
    if not button.is_disabled():
        raise RuntimeError("build button was not disabled after submit")
    if "正在生成 LLM Wiki、课程和引用索引" not in form.inner_text():
        raise RuntimeError("build pending status is missing")


def _assert_guided_autopilot_flow(page) -> None:
    form = page.locator("form[action$='/autopilot']")
    form.locator("button").click()
    page.wait_for_url("**/domains/*", timeout=5000)
    page.locator(".workflow-run-active").wait_for(state="visible", timeout=5000)
    if "任务正在执行" not in page.locator("[data-workflow-poll]").inner_text():
        raise RuntimeError("guided workflow did not expose active state")
    page.wait_for_function(
        "() => document.body.innerText.includes('资料门槛已满足')",
        timeout=8000,
    )
    text = page.locator("[data-workflow-poll]").inner_text()
    if "已成功 2 / 至少 2 份资料" not in text:
        raise RuntimeError("guided workflow did not expose the source success count")
    print("verified guided browser success workflow")


def _assert_guided_exhaustion_feedback(page) -> None:
    text = page.locator("[data-workflow-poll]").inner_text()
    if "仅成功摄取 0/2 份" not in text:
        raise RuntimeError("guided exhaustion summary is missing")
    if "手动添加可访问的 URL、Markdown/PDF" not in text:
        raise RuntimeError("guided exhaustion recovery action is missing")
    print("verified guided browser exhaustion feedback")


def _assert_llm_enhanced_intake(page) -> None:
    page.locator(".intake-panel").wait_for(state="visible", timeout=5000)
    body_text = page.locator("body").inner_text()
    if "模型建议了值得确认的学习边界" not in body_text:
        raise RuntimeError("LLM-led clarification provenance is missing")
    if "方法基础" not in body_text:
        raise RuntimeError("LLM-led clarification option is missing")
    page.locator("input[value='practice']").check()
    page.get_by_role("button", name="确认并创建项目").click()
    page.wait_for_url("**/domains/*", timeout=5000)
    if "Agent 落地实践" not in page.locator(".project-boundary").inner_text():
        raise RuntimeError("selected LLM clarification scope was not persisted")


def _assert_clear_project_intake(page) -> None:
    page.locator("input[name='name']").fill("Dataphin")
    page.get_by_role("button", name="创建项目").click()
    page.wait_for_url("**/domains/*", timeout=5000)
    page.locator(".project-boundary").wait_for(state="visible", timeout=5000)
    if "Dataphin" not in page.locator(".project-boundary").inner_text():
        raise RuntimeError("clear project did not reach its dashboard")


def _assert_mobile_project_intake(page) -> None:
    page.locator(".intake-panel").wait_for(state="visible", timeout=5000)
    if page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"):
        raise RuntimeError("mobile clarification page overflows horizontally")
    page.get_by_role("button", name="按当前默认理解继续").click()
    page.locator(".project-boundary").wait_for(state="visible", timeout=5000)
    if "数据治理 方法基础" not in page.locator(".project-boundary").inner_text():
        raise RuntimeError("mobile default clarification did not persist the recommended scope")


def _assert_mobile_no_horizontal_overflow(page) -> None:
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    if overflow:
        raise RuntimeError("dashboard overflows horizontally at mobile width")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stop_server(server: subprocess.Popen[str]) -> None:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
