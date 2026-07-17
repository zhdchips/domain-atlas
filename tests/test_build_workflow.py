from __future__ import annotations

from copy import deepcopy

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import ChunkRepository, CreateChunk, CreateSource, SourceRepository
from domain_atlas.workflow.build import KnowledgeBuildWorkflow, _normalize_payload


class FakeChatProvider:
    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    def complete_json(self, *, system_prompt: str, user_prompt: str):
        assert "encyclopedia-style" in system_prompt
        assert "S1-C1" in user_prompt
        self.user_prompts.append(user_prompt)
        return build_payload()


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


def build_payload():
    return {
        "source_profiles": [
            {
                "source_id": 1,
                "summary": "资料介绍了 Agent 的工具使用。",
                "authority_note": "测试资料。",
                "coverage_note": "覆盖基础概念。",
                "citations": ["S1-C1"],
            }
        ],
        "concepts": [
            {
                "name": "Agent",
                "definition": "能够规划并使用工具完成任务的系统。",
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
                "summary": "Agent 是能够规划并使用工具的系统。",
                "body_markdown": "## 定义\nAgent 能够规划并使用工具。[S1-C1]",
                "citations": ["S1-C1"],
            }
        ],
        "learning_guide": _learning_guide_payload(),
        "learning_modules": [
            {
                "stage": stage,
                "title": title,
                "stage_overview": f"{title}阶段先建立可直接学习的 Agent 知识框架。",
                "core_explanation": DEEP_CORE_EXPLANATION,
                "knowledge_blocks": [
                    {
                        "title": "目标与规划",
                        "body": "Agent 先把目标拆成可执行步骤，再决定是否需要工具。[S1-C1]",
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
                        "title": "工具调用例子",
                        "body": "当问题需要外部信息时，Agent 可以调用搜索或数据库工具。[S1-C1]",
                        "citations": ["S1-C1"],
                    }
                ],
                "misconceptions": [
                    {
                        "title": "把 Agent 等同于聊天",
                        "correction": "Agent 的关键在于目标驱动、工具使用和反馈闭环。[S1-C1]",
                        "citations": ["S1-C1"],
                    }
                ],
                "objectives": [f"理解{title}", "能说明工具结果如何影响下一步"],
                "readings": ["Agent [S1-C1]"],
                "key_concepts": ["Agent", "Tool Use"],
                "check_questions": ["Agent 为什么需要工具？", "工具结果如何影响计划？"],
                "practice_task": "用一句话解释 Agent。",
                "further_reading": [
                    {"title": "Agent Source", "locator": "Agent [S1-C1]", "citations": ["S1-C1"]}
                ],
                "citations": ["S1-C1"],
            }
            for stage, title in enumerate(
                STAGE_TITLES,
                start=1,
            )
        ],
    }


def _learning_guide_payload():
    return {
        "summary": "Agent 是围绕目标规划、调用工具并利用反馈完成任务的系统。[S1-C1]",
        "question_answers": [
            {
                "question": question,
                "answer": f"{question}：Agent 学习需要围绕规划、工具使用和反馈闭环展开。[S1-C1]",
                "citations": ["S1-C1"],
            }
            for question in GUIDE_QUESTIONS
        ],
        "mainline": [
            {
                "title": f"{title}：从目标到工具执行",
                "explanation": "先理解 Agent 如何把目标拆成步骤，再通过工具完成外部动作。[S1-C1]",
                "learning_outcome": "能把一个目标、所需工具和反馈闭环对应起来。",
                "module_stage": stage,
                "concept_names": ["Agent", "Tool Use"],
                "citations": ["S1-C1"],
            }
            for stage, title in enumerate(STAGE_TITLES, start=1)
        ],
        "core_concepts": [
            {
                "name": "Agent",
                "explanation": "能够规划并使用工具完成任务的系统。[S1-C1]",
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
                "name": "Tool Use",
                "description": "研究 Agent 如何选择和调用外部工具。[S1-C1]",
                "when_to_study": "理解 Agent 基本闭环之后。",
                "citations": ["S1-C1"],
            }
        ],
        "details": [
            {
                "title": "工具失败处理",
                "description": "关注工具调用失败后的重试、降级和证据保留。[S1-C1]",
                "practice_or_example": "模拟一次工具失败并写出恢复步骤。",
                "citations": ["S1-C1"],
            }
        ],
        "citations": ["S1-C1"],
    }


def test_knowledge_build_workflow_persists_artifacts(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="agent", scope="旅行代理")
    )
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="markdown",
            title="Agent Source",
            locator="fixture",
        )
    )
    ChunkRepository(database_path).replace_for_source(
        source.id,
        [
            CreateChunk(
                chunk_uid="chunk:1",
                project_id=project.id,
                source_id=source.id,
                ordinal=1,
                text="Agents plan and use tools.",
                citation_label="S1-C1",
                metadata={"source_title": "Agent Source"},
            )
        ],
    )

    chat = FakeChatProvider()
    workflow = KnowledgeBuildWorkflow(database_path=database_path, chat_provider=chat)
    workflow.run(project.id)

    repository = KnowledgeArtifactRepository(database_path)
    pages = repository.list_wiki_pages(project.id)
    guide = repository.get_learning_guide(project.id)
    modules = repository.list_learning_modules(project.id)
    updated_project = DomainProjectRepository(database_path).get(project.id)
    paths = {page.path: page for page in pages}

    assert paths["wiki/index"].title == "Wiki Index"
    assert paths["wiki/log"].page_type == "log"
    assert paths["wiki/templates/source"].page_type == "template"
    assert paths["wiki/templates/concept"].page_type == "template"
    assert any(page.page_type == "source" for page in pages)
    assert any(page.path == "wiki/concepts/agent" for page in pages)
    assert paths["wiki/synthesis/overview"].page_type == "synthesis"
    agent_page = paths["wiki/concepts/agent"]
    assert agent_page.title == "Agent"
    assert agent_page.citations == ["S1-C1"]
    assert guide is not None
    assert guide.summary.startswith("Agent 是围绕目标")
    assert [item["question"] for item in guide.question_answers] == GUIDE_QUESTIONS
    assert guide.mainline[0]["module_stage"] == 1
    assert guide.mainline[0]["concept_names"] == ["Agent", "Tool Use"]
    assert len(modules) == 5
    assert modules[0].title == "入门认知"
    assert modules[0].stage_overview.startswith("入门认知阶段")
    assert len(modules[0].core_explanation) >= 180
    assert modules[0].knowledge_blocks[0]["title"] == "目标与规划"
    assert len(modules[0].knowledge_blocks) == 3
    assert modules[0].examples[0]["title"] == "工具调用例子"
    assert modules[0].misconceptions[0]["title"] == "把 Agent 等同于聊天"
    assert modules[0].further_reading[0]["title"] == "Agent Source"
    assert updated_project is not None
    assert updated_project.build_status == "completed"
    assert "Domain: 旅行代理" in chat.user_prompts[0]


def test_normalize_payload_derives_mainline_navigation_for_legacy_guide():
    payload = build_payload()
    for item in payload["learning_guide"]["mainline"]:
        item.pop("module_stage")
        item.pop("learning_outcome")
        item.pop("concept_names")

    normalized = _normalize_payload(payload)
    mainline = normalized["learning_guide"]["mainline"]

    assert mainline[0]["module_stage"] == 1
    assert mainline[0]["learning_outcome"].startswith("先理解 Agent")
    assert mainline[0]["concept_names"] == ["Agent", "Tool Use"]


def test_knowledge_build_retries_once_for_shallow_lesson_payload(tmp_path):
    class RepairingChatProvider:
        def __init__(self) -> None:
            self.calls = 0

        def complete_json(self, *, system_prompt: str, user_prompt: str):
            self.calls += 1
            if self.calls == 1:
                shallow = deepcopy(build_payload())
                shallow["learning_modules"][0]["knowledge_blocks"] = shallow["learning_modules"][0][
                    "knowledge_blocks"
                ][:1]
                return shallow
            assert "failed the lesson-quality contract" in user_prompt
            return build_payload()

    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="LLM Agents"))
    source = SourceRepository(database_path).create(
        CreateSource(project_id=project.id, source_type="markdown", title="Agent Source", locator="fixture")
    )
    ChunkRepository(database_path).replace_for_source(
        source.id,
        [
            CreateChunk(
                chunk_uid="chunk:1",
                project_id=project.id,
                source_id=source.id,
                ordinal=1,
                text="Agents plan and use tools.",
                citation_label="S1-C1",
                metadata={"source_title": "Agent Source"},
            )
        ],
    )

    provider = RepairingChatProvider()
    KnowledgeBuildWorkflow(database_path=database_path, chat_provider=provider).run(project.id)

    assert provider.calls == 2
    modules = KnowledgeArtifactRepository(database_path).list_learning_modules(project.id)
    assert len(modules[0].knowledge_blocks) == 3
