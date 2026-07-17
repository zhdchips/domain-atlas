from __future__ import annotations

import time

from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.discovery.exa import SourceDiscoveryError
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.intake.assessment import IntakeAssessment
from domain_atlas.domain.source_candidates import SourceCandidateDraft
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.providers.vector_index import RetrievedChunk, RetrievedWikiSection
from domain_atlas.web.app import create_app


GUIDE_QUESTIONS = [
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

STAGE_TITLES = ["入门认知", "核心概念", "关键方法", "实践应用", "进阶专题"]
DEEP_CORE_EXPLANATION = (
    "Agent 的学习重点不是把模型当作会回答问题的聊天界面，而是理解它如何围绕明确目标形成行动闭环。"
    "它先把任务分解为可验证的步骤，判断哪些信息或动作需要外部工具，再读取工具返回的结果并修正后续计划。"
    "这个循环让系统能够把语言理解转化为检索、计算、写入等实际操作，同时也要求每一步保留证据和失败处理策略。"
    "学习者应能区分模型生成的建议与工具执行得到的事实，并据此评估一次任务是否真的完成。[S1-C1]"
)


class FakeDiscoveryProvider:
    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        assert query
        assert limit == 12
        return [
            SourceCandidateDraft(
                provider="exa",
                provider_source_id="src-1",
                title="Agent Docs",
                url="https://docs.example.com/agents",
                snippet="Official docs for agents.",
                source_type="official_docs",
                publisher="Example Docs",
                published_at="2026-01-01",
                authority_score=0.9,
                authority_reason="官方资料",
            )
        ]


class FailingDiscoveryProvider:
    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        raise SourceDiscoveryError("搜索服务暂时不可用")


class FakeIntakeAssessmentProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def assess(self, *, name: str, goal: str, level: str) -> IntakeAssessment:
        self.calls.append(name)
        if name == "Dataphin":
            return IntakeAssessment(
                needs_clarification=False,
                reason="边界已清楚。",
                understanding="“Dataphin”已给出明确产品领域和入门目标。",
                question="",
                options=[],
                default_scope="Dataphin",
                assumptions=["按提交领域建立地图。"],
                confidence=0.93,
            )
        return IntakeAssessment(
            needs_clarification=True,
            reason="领域有多个常见学习切入面。",
            understanding=f"“{name}”需要先确认具体学习方向。",
            question=f"你最希望先从{name}的哪个切入面学习？",
            options=[
                {
                    "value": "foundations",
                    "label": "方法基础",
                    "description": "理解核心概念、方法论和关键流程。",
                    "scope": f"{name} 方法基础",
                },
                {
                    "value": "practice",
                    "label": "落地实践",
                    "description": "从组织落地、案例和实践方法进入。",
                    "scope": f"{name} 落地实践",
                }
            ],
            default_scope=f"{name} 方法基础",
            assumptions=["确认后将以选择的范围组织资料和课程。"],
            confidence=0.87,
            recommended_option="foundations",
        )


class FailingIntakeAssessmentProvider:
    def assess(self, **kwargs):
        raise TimeoutError("provider api key should never be shown")


class InvalidIntakeAssessmentProvider:
    def assess(self, **kwargs):
        return None


class LowConfidenceIntakeAssessmentProvider:
    def assess(self, *, name: str, **kwargs):
        return IntakeAssessment(
            needs_clarification=True,
            reason="模型对范围判断不够确定。",
            understanding=f"“{name}”可能有多个方向。",
            question="你希望从哪里开始？",
            options=[
                {"value": "a", "label": "A", "description": "方向 A", "scope": f"{name} A"},
                {"value": "b", "label": "B", "description": "方向 B", "scope": f"{name} B"},
            ],
            default_scope=f"{name} A",
            assumptions=[],
            confidence=0.2,
            recommended_option="a",
        )


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(len(text))] for text in texts]


class FakeVectorIndex:
    def __init__(self):
        self.calls = []

    def upsert_chunks(self, *, project_id: int, chunks, embeddings) -> None:
        self.calls.append((project_id, len(chunks), len(embeddings)))

    def upsert_wiki_sections(self, *, project_id: int, sections, embeddings) -> None:
        self.calls.append(("wiki", project_id, len(sections), len(embeddings)))

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedChunk(
                chunk_uid="chunk:1",
                text="Agents use tools.",
                citation_label="S1-C1",
                source_id=1,
                distance=0.1,
                metadata={},
            )
        ]

    def query_wiki_sections(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedWikiSection(
                section_uid="agent#1",
                page_slug="agent",
                heading="Agent",
                body_markdown="Agent 会使用工具完成任务。",
                citations=["W:agent#1"],
                source_chunk_uids=["chunk:1"],
                source_citation_labels=["S1-C1"],
                distance=0.1,
                metadata={},
            )
        ]


class FakeChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "source_profiles": [
                {
                    "source_id": 1,
                    "summary": "资料介绍 Agent。",
                    "authority_note": "测试资料。",
                    "coverage_note": "基础覆盖。",
                    "citations": ["S1-C1"],
                }
            ],
            "concepts": [
                {
                    "name": "Agent",
                    "definition": "Agent 使用工具完成任务。",
                    "prerequisites": [],
                    "related": ["Tool Use"],
                    "citations": ["S1-C1"],
                }
            ],
            "concept_edges": [
                {
                    "source": "Agent",
                    "target": "Tool Use",
                    "relation": "related",
                    "citations": ["S1-C1"],
                }
            ],
            "wiki_pages": [
                {
                    "title": "Agent",
                    "topic_path": "核心概念/Agent",
                    "summary": "Agent 使用工具完成任务。",
                    "body_markdown": "## Agent\nAgent 使用工具完成任务。[S1-C1]",
                    "citations": ["S1-C1"],
                }
            ],
            "learning_guide": {
                "summary": "Agent 是使用工具完成任务的目标导向系统。[S1-C1]",
                "question_answers": [
                    {
                        "question": question,
                        "answer": f"{question}：Agent 通过规划、工具调用和反馈来完成任务。[S1-C1]",
                        "citations": ["S1-C1"],
                    }
                    for question in GUIDE_QUESTIONS
                ],
                "mainline": [
                    {
                        "title": f"{title}：目标、规划、工具、反馈",
                        "explanation": "学习主线从目标拆解进入工具调用，再理解反馈修正。[S1-C1]",
                        "learning_outcome": "能说明目标、工具和反馈如何组成行动闭环。",
                        "module_stage": stage,
                        "concept_names": ["Agent", "Tool Use"],
                        "citations": ["S1-C1"],
                    }
                    for stage, title in enumerate(STAGE_TITLES, start=1)
                ],
                "core_concepts": [
                    {
                        "name": "Agent",
                        "explanation": "Agent 使用工具完成任务。[S1-C1]",
                        "depends_on": [],
                        "citations": ["S1-C1"],
                    }
                    ,
                    {
                        "name": "Tool Use",
                        "explanation": "让 Agent 连接外部检索、计算和执行能力的机制。[S1-C1]",
                        "depends_on": ["Agent"],
                        "citations": ["S1-C1"],
                    }
                ],
                "branches": [
                    {
                        "name": "工具使用",
                        "description": "关注 Agent 如何选择并调用工具。[S1-C1]",
                        "when_to_study": "掌握基础定义后。",
                        "citations": ["S1-C1"],
                    }
                ],
                "details": [
                    {
                        "title": "反馈修正",
                        "description": "Agent 根据工具结果调整下一步动作。[S1-C1]",
                        "practice_or_example": "解释一次工具调用后的反馈修正。",
                        "citations": ["S1-C1"],
                    }
                ],
                "citations": ["S1-C1"],
            },
            "learning_modules": [
                {
                    "stage": stage,
                    "title": title,
                    "stage_overview": f"{title}阶段把 Agent 的目标、规划和工具使用串起来。",
                    "core_explanation": DEEP_CORE_EXPLANATION,
                    "knowledge_blocks": [
                        {
                            "title": "规划与工具",
                            "body": "Agent 先判断任务目标，再选择合适工具完成外部动作。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                        {
                            "title": "工具选择",
                            "body": "工具调用把语言任务连接到检索、计算或写入等外部动作，工具类型必须和待验证的步骤匹配。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                        {
                            "title": "反馈与证据",
                            "body": "工具结果会改变下一步计划；可靠流程还要记录来源和失败原因，避免把猜测当成已经执行的事实。[S1-C1]",
                            "citations": ["S1-C1"],
                        },
                    ],
                    "examples": [
                        {
                            "title": "检索型 Agent",
                            "body": "需要外部资料时，Agent 可以检索资料并把结果纳入回答。[S1-C1]",
                            "citations": ["S1-C1"],
                        }
                    ],
                    "misconceptions": [
                        {
                            "title": "只看对话不看证据",
                            "correction": "可靠 Agent 学习应保留 citation 和 provenance。[S1-C1]",
                            "citations": ["S1-C1"],
                        }
                    ],
                    "objectives": ["建立理解", "说明工具结果如何影响下一步"],
                    "readings": ["Agent [S1-C1]"],
                    "key_concepts": ["Agent", "Tool Use"],
                    "check_questions": ["什么是 Agent？", "工具结果如何影响计划？"],
                    "practice_task": "解释 Agent。",
                    "further_reading": [
                        {"title": "Agent Wiki", "locator": "wiki/concepts/agent", "citations": ["S1-C1"]}
                    ],
                    "citations": ["S1-C1"],
                }
                for stage, title in enumerate(
                    STAGE_TITLES,
                    start=1,
                )
            ],
        }


class FakeQAChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "W:agent#1" in user_prompt
        return {
            "answer": "Agent 会使用工具完成任务。",
            "citations": ["W:agent#1"],
            "evidence_status": "sufficient",
        }


def test_health_route_returns_ok(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Domain Atlas"}


def test_home_route_renders_skeleton(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Domain Atlas" in response.text
    assert "创建领域项目" in response.text


def test_create_domain_redirects_to_dashboard(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/domains",
        data={
            "name": "LLM Agents",
            "goal": "建立系统化知识地图",
            "level": "beginner",
            "language": "zh",
            "interaction_mode": "expert",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert dashboard.status_code == 200
    assert "LLM Agents" in dashboard.text
    assert "建立系统化知识地图" in dashboard.text
    assert "expert" in dashboard.text
    assert "学习路线" in dashboard.text


def test_llm_assessment_enters_clarification_then_persists_selected_scope(tmp_path):
    provider = FakeIntakeAssessmentProvider()
    app = create_app(Settings(data_dir=tmp_path), intake_assessment_provider=provider)
    client = TestClient(app)

    created = client.post(
        "/domains",
        data={"name": "Agent", "goal": "", "level": "beginner", "interaction_mode": "guided"},
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == "/domains/1/intake"
    clarification = client.get(created.headers["location"])
    assert "确认领域边界" in clarification.text
    assert "模型建议了值得确认的学习边界" in clarification.text
    assert "方法基础" in clarification.text
    assert "按当前默认理解继续" in clarification.text

    confirmed = client.post(
        "/domains/1/intake",
        data={"selection": "practice"},
        follow_redirects=False,
    )

    assert confirmed.status_code == 303
    assert confirmed.headers["location"].startswith("/domains/1")
    dashboard = client.get(confirmed.headers["location"])
    assert "Agent 落地实践" in dashboard.text
    assert "建立可溯源的入门领域地图" in dashboard.text
    assert "初始化状态" in dashboard.text
    assert "已确认" in dashboard.text


def test_llm_assessment_decides_clear_or_clarify_for_semantic_domains(tmp_path):
    provider = FakeIntakeAssessmentProvider()
    app = create_app(Settings(data_dir=tmp_path), intake_assessment_provider=provider)
    client = TestClient(app)

    clear = client.post("/domains", data={"name": "Dataphin"}, follow_redirects=False)
    data_governance = client.post("/domains", data={"name": "数据治理"}, follow_redirects=False)
    product_ops = client.post("/domains", data={"name": "产品运营"}, follow_redirects=False)

    assert clear.headers["location"] == "/domains/1"
    assert data_governance.headers["location"] == "/domains/2/intake"
    assert product_ops.headers["location"] == "/domains/3/intake"
    assert provider.calls == ["Dataphin", "数据治理", "产品运营"]
    clarification = client.get(data_governance.headers["location"])
    assert "你最希望先从数据治理的哪个切入面学习" in clarification.text
    assert "方法基础" in clarification.text
    project = DomainProjectRepository(tmp_path / "domain_atlas.sqlite3").get(2)
    assert project is not None
    assert project.intake_metadata["reason"] == "领域有多个常见学习切入面。"
    assert project.intake_metadata["assessment_source"] == "llm"
    assert project.intake_metadata["assessment_status"] == "applied"
    assert project.intake_metadata["confidence"] == 0.87


def test_failed_or_unconfigured_intake_assessment_falls_back_without_raw_error(tmp_path):
    failing_app = create_app(
        Settings(data_dir=tmp_path / "failed"),
        intake_assessment_provider=FailingIntakeAssessmentProvider(),
    )
    failing_client = TestClient(failing_app)
    failed = failing_client.post("/domains", data={"name": "Agent"}, follow_redirects=False)
    fallback_page = failing_client.get(failed.headers["location"])
    failed_project = DomainProjectRepository(tmp_path / "failed" / "domain_atlas.sqlite3").get(1)

    assert failed.headers["location"] == "/domains/1"
    assert "provider api key" not in fallback_page.text
    assert failed_project is not None
    assert failed_project.scope == "Agent"
    assert failed_project.intake_metadata["assessment_source"] == "fallback"
    assert failed_project.intake_metadata["assessment_status"] == "failed"

    unconfigured_app = create_app(
        Settings(
            data_dir=tmp_path / "unconfigured",
            intake_llm_assessment_enabled=True,
            llm_api_key="",
            llm_base_url="",
        )
    )
    unconfigured_client = TestClient(unconfigured_app)
    unconfigured = unconfigured_client.post("/domains", data={"name": "Agent"}, follow_redirects=False)
    unconfigured_project = DomainProjectRepository(tmp_path / "unconfigured" / "domain_atlas.sqlite3").get(1)

    assert unconfigured.status_code == 303
    assert unconfigured.headers["location"] == "/domains/1"
    assert unconfigured_project is not None
    assert unconfigured_project.intake_metadata["assessment_source"] == "fallback"
    assert unconfigured_project.intake_metadata["assessment_status"] == "unconfigured"


def test_invalid_or_low_confidence_assessment_falls_back_to_direct_creation(tmp_path):
    invalid_client = TestClient(
        create_app(
            Settings(data_dir=tmp_path / "invalid"),
            intake_assessment_provider=InvalidIntakeAssessmentProvider(),
        )
    )
    invalid = invalid_client.post("/domains", data={"name": "产品运营"}, follow_redirects=False)
    invalid_project = DomainProjectRepository(tmp_path / "invalid" / "domain_atlas.sqlite3").get(1)

    low_client = TestClient(
        create_app(
            Settings(data_dir=tmp_path / "low"),
            intake_assessment_provider=LowConfidenceIntakeAssessmentProvider(),
        )
    )
    low = low_client.post("/domains", data={"name": "数据治理"}, follow_redirects=False)
    low_project = DomainProjectRepository(tmp_path / "low" / "domain_atlas.sqlite3").get(1)

    assert invalid.headers["location"] == "/domains/1"
    assert invalid_project is not None
    assert invalid_project.scope == "产品运营"
    assert invalid_project.intake_metadata["assessment_status"] == "invalid"
    assert low.headers["location"] == "/domains/1"
    assert low_project is not None
    assert low_project.scope == "数据治理"
    assert low_project.intake_metadata["assessment_status"] == "low_confidence"


def test_legacy_clarification_metadata_remains_confirmable(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(
            name="旧项目",
            scope="旧项目默认范围",
            intake_status="needs_clarification",
            intake_metadata={
                "reason": "ambiguous_domain",
                "understanding": "旧项目需要确认范围。",
                "question": "你希望从哪里开始？",
                "options": [
                    {
                        "value": "legacy_scope",
                        "label": "旧范围",
                        "description": "使用历史保存的范围。",
                        "scope": "旧项目历史范围",
                    }
                ],
                "default_scope": "旧项目默认范围",
                "assumptions": ["历史项目。"],
                "suggestion_source": "llm",
                "suggestion_status": "applied",
            },
        )
    )
    client = TestClient(app)

    page = client.get(f"/domains/{project.id}/intake")
    confirmed = client.post(
        f"/domains/{project.id}/intake",
        data={"selection": "legacy_scope"},
        follow_redirects=False,
    )
    confirmed_project = DomainProjectRepository(settings.database_path).get(project.id)

    assert page.status_code == 200
    assert "旧范围" in page.text
    assert confirmed.headers["location"].startswith(f"/domains/{project.id}")
    assert confirmed_project is not None
    assert confirmed_project.scope == "旧项目历史范围"
    assert confirmed_project.intake_metadata["assessment_source"] == "llm"


def test_intake_allows_custom_scope_or_default_and_keeps_expert_manual(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), intake_assessment_provider=FakeIntakeAssessmentProvider())
    client = TestClient(app)

    broad = client.post(
        "/domains",
        data={"name": "数据治理", "goal": "行业落地", "interaction_mode": "expert"},
        follow_redirects=False,
    )
    custom = client.post(
        "/domains/1/intake",
        data={"selection": "default", "custom_scope": "医疗 AI 的临床决策支持"},
        follow_redirects=False,
    )
    custom_dashboard = client.get(custom.headers["location"])
    assert "医疗 AI 的临床决策支持" in custom_dashboard.text
    assert "专家模式" not in custom_dashboard.text
    assert "workflow-run" not in custom_dashboard.text

    ambiguous = client.post("/domains", data={"name": "产品运营"}, follow_redirects=False)
    default = client.post("/domains/2/intake", data={"selection": "default"}, follow_redirects=False)
    default_dashboard = client.get(default.headers["location"])
    assert "产品运营 方法基础" in default_dashboard.text
    assert "已按系统当前推荐理解继续" in default_dashboard.text


def test_home_lists_existing_projects(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    client.post("/domains", data={"name": "合成生物学"})

    response = client.get("/")

    assert response.status_code == 200
    assert "合成生物学" in response.text
    assert "/domains/1" in response.text


def test_missing_domain_returns_404(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/domains/404")

    assert response.status_code == 404


def test_discover_sources_lists_candidates_and_confirm_accepts(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), discovery_provider=FakeDiscoveryProvider())
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    discover = client.post(
        "/domains/1/discover",
        data={"query": ""},
        follow_redirects=False,
    )

    assert discover.status_code == 303
    assert discover.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert "Agent Docs" in dashboard.text
    assert "Official docs for agents." in dashboard.text
    assert "官方资料" in dashboard.text

    confirm = client.post(
        "/domains/1/candidates/1/confirm",
        follow_redirects=False,
    )

    assert confirm.status_code == 303
    accepted_dashboard = client.get("/domains/1")
    assert "已确认" in accepted_dashboard.text
    assert "Agent Docs" in accepted_dashboard.text
    assert "pending" in accepted_dashboard.text


def test_add_url_source_route_lists_pending_source(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    response = client.post(
        "/domains/1/sources/url",
        data={"url": "https://docs.example.com/agents", "title": "Agent Docs"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    dashboard = client.get("/domains/1")
    assert "Agent Docs" in dashboard.text
    assert "https://docs.example.com/agents" in dashboard.text
    assert "pending" in dashboard.text


def test_form_error_redirects_to_dashboard_instead_of_exposing_json(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), discovery_provider=FailingDiscoveryProvider())
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    response = client.post("/domains/1/discover", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/domains/1?error=")
    dashboard = client.get(response.headers["location"])
    assert "搜索候选资料失败：搜索服务暂时不可用" in dashboard.text
    assert '{"detail"' not in dashboard.text


def test_upload_markdown_and_ingest_from_dashboard(tmp_path):
    vector_index = FakeVectorIndex()
    app = create_app(
        Settings(data_dir=tmp_path),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    upload = client.post(
        "/domains/1/sources/file",
        files={"file": ("agents.md", b"# Agents\n\nAgents use tools.", "text/markdown")},
        follow_redirects=False,
    )

    assert upload.status_code == 303
    before = client.get("/domains/1")
    assert "agents" in before.text
    assert "pending" in before.text

    ingest = client.post("/domains/1/sources/1/ingest", follow_redirects=False)

    assert ingest.status_code == 303
    _wait_for_workflow(tmp_path / "domain_atlas.sqlite3", project_id=1)
    after = client.get("/domains/1")
    assert "已摄取" in after.text
    assert "Chunks" in after.text
    assert vector_index.calls == [(1, 1, 1)]


def test_build_knowledge_route_renders_wiki_and_learning_path(tmp_path):
    vector_index = FakeVectorIndex()
    app = create_app(
        Settings(data_dir=tmp_path),
        chat_provider=FakeChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})
    client.post(
        "/domains/1/sources/file",
        files={"file": ("agents.md", b"# Agents\n\nAgents use tools.", "text/markdown")},
    )
    client.post("/domains/1/sources/1/ingest")
    _wait_for_workflow(tmp_path / "domain_atlas.sqlite3", project_id=1)

    build = client.post("/domains/1/build", follow_redirects=False)

    assert build.status_code == 303
    _wait_for_workflow(tmp_path / "domain_atlas.sqlite3", project_id=1)
    dashboard = client.get("/domains/1")
    assert "completed" in dashboard.text
    wiki = client.get("/domains/1/wiki")
    assert "Agent 使用工具完成任务" in wiki.text
    assert "LLM Wiki Workspace" in wiki.text
    assert "wiki/index" in wiki.text
    assert 'href="/domains/1/wiki/index"' in wiki.text
    assert "/domains/1/wiki/wiki/index" not in wiki.text
    assert "templates" in wiki.text
    assert client.get("/domains/1/wiki/index").status_code == 200
    assert client.get("/domains/1/wiki/wiki/index").status_code == 200
    path = client.get("/domains/1/path")
    assert "学习导览" in path.text
    assert "领域速览" in path.text
    assert "关键问题" in path.text
    assert "领域主线" in path.text
    assert "本阶段将掌握" in path.text
    assert "进入第 1 阶段学习" in path.text
    assert 'href="#lesson-stage-1"' in path.text
    assert 'href="/domains/1/wiki/concepts/agent"' in path.text
    assert "支线拓展" in path.text
    assert "为什么存在" in path.text
    assert "目标、规划、工具、反馈" in path.text
    assert "阶段定位" in path.text
    assert "核心讲解" in path.text
    assert "知识块" in path.text
    assert "规划与工具" in path.text
    assert "工具选择" in path.text
    assert "反馈与证据" in path.text
    assert "例子 / 案例" in path.text
    assert "检索型 Agent" in path.text
    assert "常见误区" in path.text
    assert "只看对话不看证据" in path.text
    assert "证据来源 / 深入阅读" in path.text
    assert "阅读材料" not in path.text
    assert "入门认知" in path.text
    assert "进阶专题" in path.text
    assert 'id="lesson-stage-1"' in path.text
    assert any(call[0] == "wiki" and call[1] == 1 and call[2] >= 7 for call in vector_index.calls)


def test_qa_route_records_cited_answer(tmp_path):
    app = create_app(
        Settings(data_dir=tmp_path),
        chat_provider=FakeQAChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    response = client.post(
        "/domains/1/qa",
        data={"question": "Agent 是什么？"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    qa_page = client.get("/domains/1/qa")
    assert "Agent 会使用工具完成任务" in qa_page.text
    assert "W:agent#1" in qa_page.text
    assert "S1-C1" in qa_page.text


def _wait_for_workflow(database_path, *, project_id: int) -> None:
    deadline = time.monotonic() + 3
    repository = WorkflowRepository(database_path)
    while time.monotonic() < deadline:
        runs = repository.list_for_project(project_id, limit=3)
        if runs and not any(run.status in {"queued", "running"} for run in runs):
            return
        time.sleep(0.02)
    raise AssertionError("background workflow did not finish in time")
