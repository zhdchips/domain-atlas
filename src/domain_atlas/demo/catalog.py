"""Curated in-memory catalog used only by ``PUBLIC_DEMO_MODE``."""

from __future__ import annotations

from dataclasses import dataclass

from domain_atlas.domain.artifacts import LearningGuide, LearningModule, WikiPage
from domain_atlas.domain.projects import DomainProject
from domain_atlas.domain.qa import QARecord


@dataclass(frozen=True)
class DemoSource:
    title: str
    publisher: str
    url: str
    source_type: str
    coverage: str
    citations: list[str]


@dataclass(frozen=True)
class PublicDemoCatalog:
    project: DomainProject
    sources: list[DemoSource]
    pages: list[WikiPage]
    guide: LearningGuide
    modules: list[LearningModule]
    qa_records: list[QARecord]

    @property
    def page_groups(self) -> dict[str, list[WikiPage]]:
        groups: dict[str, list[WikiPage]] = {}
        for page in self.pages:
            groups.setdefault(page.page_type, []).append(page)
        return groups


def public_demo_catalog() -> PublicDemoCatalog:
    """Return stable portfolio content without reading runtime storage or providers."""

    project = DomainProject(
        id=0,
        name="Agent Harness Engineering",
        goal="理解如何把 LLM Agent 做成可观测、可评测、可恢复的业务系统。",
        level="intermediate",
        language="zh",
        interaction_mode="guided",
        scope="Agent Harness Engineering",
        intake_status="confirmed",
        intake_metadata={"assumptions": ["演示内容为预构建的公开只读样例。"]},
        status="demo",
        build_status="completed",
        created_at="2026-07-18T00:00:00Z",
        updated_at="2026-07-18T00:00:00Z",
    )
    sources = [
        DemoSource(
            title="OpenAI Agents SDK documentation",
            publisher="OpenAI",
            url="https://openai.github.io/openai-agents-python/",
            source_type="official_docs",
            coverage="Agent loop、工具调用、handoff 与 tracing 的实现接口。",
            citations=["S1-C1"],
        ),
        DemoSource(
            title="LangGraph overview",
            publisher="LangChain",
            url="https://langchain-ai.github.io/langgraph/",
            source_type="official_docs",
            coverage="长任务状态、可恢复编排与人工介入的状态机视角。",
            citations=["S2-C1"],
        ),
        DemoSource(
            title="Building effective agents",
            publisher="Anthropic",
            url="https://www.anthropic.com/engineering/building-effective-agents",
            source_type="engineering_article",
            coverage="何时使用 workflow、何时使用 agent，以及逐步增加自治性的工程原则。",
            citations=["S3-C1"],
        ),
    ]
    pages = [
        _page(
            page_id=1,
            slug="index",
            page_type="index",
            path="wiki/index",
            title="Harness Map",
            summary="Agent Harness 把模型能力约束在可观测的执行边界中。",
            body=(
                "# Harness Map\n\n"
                "Agent Harness 不是另一个模型，而是围绕目标、工具、状态、证据和评测建立的运行环境。"
                "它让一次模型调用能够被追踪、复现、限制成本，并在失败时恢复。[S1-C1][S2-C1]\n\n"
                "- [[Agent Loop]]\n- [[Tool Contracts]]\n- [[Evaluation and Trace]]"
            ),
            citations=["S1-C1", "S2-C1"],
        ),
        _page(
            page_id=2,
            slug="agent-loop",
            page_type="concept",
            path="wiki/concepts/agent-loop",
            title="Agent Loop",
            summary="将目标拆解、工具执行、观察结果和下一步决策组织成有限循环。",
            body=(
                "# Agent Loop\n\n"
                "可靠的 loop 会把每次工具调用看成可验证的状态转换：先声明目标和输入，"
                "再执行工具、读取观察结果、判断是否继续或终止。模型负责局部判断，"
                "Harness 负责上限、状态与证据边界。[S1-C1][S3-C1]"
            ),
            citations=["S1-C1", "S3-C1"],
        ),
        _page(
            page_id=3,
            slug="tool-contracts",
            page_type="concept",
            path="wiki/concepts/tool-contracts",
            title="Tool Contracts",
            summary="工具的输入、输出、权限、超时和失败语义应当显式化。",
            body=(
                "# Tool Contracts\n\n"
                "工具不是给模型的一段自由文本，而是受 schema、权限与超时约束的接口。"
                "稳定 contract 能让 planner 的选择、executor 的调用和 verifier 的判断共享同一份事实。"
                "[S1-C1][S2-C1]"
            ),
            citations=["S1-C1", "S2-C1"],
        ),
        _page(
            page_id=4,
            slug="evaluation-trace",
            page_type="synthesis",
            path="wiki/synthesis/evaluation-trace",
            title="Evaluation and Trace",
            summary="用 Trace 记录运行事实，用评测集判断系统是否持续满足任务目标。",
            body=(
                "# Evaluation and Trace\n\n"
                "Trace 回答一次任务实际上发生了什么：调用了哪些工具、花了多久、证据是否充足。"
                "评测则回答这种行为是否正确、稳定且值得上线。二者共同把 Agent 从演示变成可治理系统。"
                "[S2-C1][S3-C1]"
            ),
            citations=["S2-C1", "S3-C1"],
        ),
        _page(
            page_id=5,
            slug="source-openai-agents",
            page_type="source",
            path="wiki/sources/openai-agents-sdk",
            title="OpenAI Agents SDK source profile",
            summary="官方资料提供 Agent、工具与 tracing 的接口层证据。",
            body=(
                "# OpenAI Agents SDK source profile\n\n"
                "该来源用于核验 Agent loop、工具调用和 tracing 等实现概念；"
                "它是证据层，不替代本 Demo 的课程组织。[S1-C1]"
            ),
            citations=["S1-C1"],
        ),
    ]
    guide = LearningGuide(
        id=1,
        project_id=0,
        summary="Agent Harness Engineering 研究如何用状态、工具契约、Trace 与评测，把模型能力组织为可控的执行系统。[S1-C1][S2-C1]",
        question_answers=[
            _question("是什么", "它是围绕 Agent 执行循环建立的工程运行环境，而不是单个模型或 prompt。[S1-C1]"),
            _question("为什么存在", "开放式模型输出不天然具备权限、成本、状态和可复现性边界，Harness 用工程约束补齐这些边界。[S2-C1]"),
            _question("如何工作", "系统把目标、状态和工具 contract 交给受限 loop；每步写入 Trace，并由评测与 verifier 检查结果。[S1-C1][S2-C1]"),
            _question("有哪些组成", "核心包括状态机、工具契约、上下文策略、Trace、评测集、失败恢复与人类介入点。[S1-C1][S2-C1]"),
            _question("有哪些流派/类型/方法论分支", "可区分确定性 workflow、有限自治 agent，以及多 agent 协作；应从简单 workflow 开始增加自治性。[S3-C1]"),
            _question("代表人物/组织/关键贡献者", "OpenAI、Anthropic、LangChain 等组织分别提供了 Agent SDK、工程实践和状态图编排的公开材料。[S1-C1][S2-C1][S3-C1]"),
            _question("经典案例", "客服检索、跨系统排障和研究任务常用 Harness 将检索、工具调用、验证和最终回答拆开治理。[S2-C1]"),
            _question("最佳实践", "优先定义明确 contract 和成功标准，限制工具权限与循环次数，并把 Trace 和版本化评测作为发布门槛。[S1-C1][S3-C1]"),
            _question("失败案例/常见误区", "把多步骤 prompt 当作可靠 agent、没有证据校验就执行写操作、或只看最终答案不看 Trace，都会掩盖真实风险。[S2-C1]"),
            _question("未来趋势", "更成熟的 Harness 会强化成本感知编排、可恢复状态、评测驱动发布和人机协作，而非无限扩大模型自主性。[S2-C1][S3-C1]"),
        ],
        mainline=[
            _mainline(1, "先定义执行边界", "理解为什么先有受控 workflow，后有有限自治。", ["Agent Loop"]),
            _mainline(2, "建立工具契约", "把输入、输出、失败与权限变成可验证接口。", ["Tool Contracts"]),
            _mainline(3, "组织状态与上下文", "让每一步读取必要事实，并留下可恢复状态。", ["Agent Loop", "Tool Contracts"]),
            _mainline(4, "接入 Trace 与 verifier", "用运行证据解释一次任务如何完成或失败。", ["Evaluation and Trace"]),
            _mainline(5, "用评测驱动迭代", "将离线任务集、成本和稳定性变成发布标准。", ["Evaluation and Trace"]),
        ],
        core_concepts=[
            {"name": "Agent Loop", "explanation": "受限地重复计划、调用工具、观察并终止。", "depends_on": ["Tool Contracts"], "citations": ["S1-C1"]},
            {"name": "Tool Contracts", "explanation": "显式描述工具的 schema、权限和失败语义。", "depends_on": [], "citations": ["S1-C1", "S2-C1"]},
            {"name": "Evaluation and Trace", "explanation": "用运行事实与版本化评测治理 Agent 行为。", "depends_on": ["Agent Loop"], "citations": ["S2-C1"]},
        ],
        branches=[
            {"name": "Multi-agent", "description": "当角色或上下文边界明显时，再用协调协议拆分责任。", "when_to_study": "掌握单 Agent 可观测 loop 后。", "citations": ["S2-C1"]},
            {"name": "Human-in-the-loop", "description": "对高风险动作设置审批点与可恢复状态。", "when_to_study": "工具将产生外部副作用时。", "citations": ["S2-C1"]},
        ],
        details=[
            {"title": "预算与超时", "description": "每个工具和整个任务都应有时间、token 与调用次数预算。", "practice_or_example": "为 loop 设置最大工具轮数并记录终止原因。", "citations": ["S1-C1"]},
            {"title": "失败恢复", "description": "区分可重试网络失败与需要用户介入的权限/证据失败。", "practice_or_example": "为 provider request 记录 retry、recovered 和 failed 事件。", "citations": ["S2-C1"]},
        ],
        citations=["S1-C1", "S2-C1", "S3-C1"],
        created_at="2026-07-18T00:00:00Z",
    )
    modules = [_module(stage, title, concept, citation) for stage, title, concept, citation in [
        (1, "为什么 Agent 需要 Harness", "Agent Loop", "S3-C1"),
        (2, "把工具变成可验证契约", "Tool Contracts", "S1-C1"),
        (3, "管理状态、上下文与终止", "Agent Loop", "S2-C1"),
        (4, "用 Trace 解释执行过程", "Evaluation and Trace", "S2-C1"),
        (5, "用评测治理上线迭代", "Evaluation and Trace", "S3-C1"),
    ]]
    qa_records = [
        QARecord(
            id=1,
            project_id=0,
            question="为什么 Agent Harness 不等于一个更长的 prompt？",
            answer="Prompt 只能影响一次生成；Harness 则定义状态如何保存、工具如何被限制、失败如何恢复，以及结果如何被 Trace 和评测验证。因此它提供的是运行时治理边界，而不只是文本指令。[W:agent-loop#1][W:evaluation-trace#1]",
            citations=["W:agent-loop#1", "W:evaluation-trace#1"],
            source_provenance=["S1-C1", "S2-C1"],
            evidence_status="supported",
            created_at="2026-07-18T00:00:00Z",
        ),
        QARecord(
            id=2,
            project_id=0,
            question="什么时候应该停止增加 Agent 自主性？",
            answer="当任务目标、工具 contract 或评测标准尚未明确时，应先使用确定性 workflow。只有在工具选择或步骤顺序确实需要模型判断，并且 Trace、预算与失败恢复已经可观测时，才逐步增加自治性。[W:tool-contracts#1][W:evaluation-trace#1]",
            citations=["W:tool-contracts#1", "W:evaluation-trace#1"],
            source_provenance=["S2-C1", "S3-C1"],
            evidence_status="supported",
            created_at="2026-07-18T00:00:00Z",
        ),
    ]
    return PublicDemoCatalog(
        project=project,
        sources=sources,
        pages=pages,
        guide=guide,
        modules=modules,
        qa_records=qa_records,
    )


def _page(
    *, page_id: int, slug: str, page_type: str, path: str, title: str, summary: str, body: str, citations: list[str]
) -> WikiPage:
    return WikiPage(
        id=page_id,
        project_id=0,
        slug=slug,
        page_type=page_type,
        path=path,
        title=title,
        topic_path=path.removeprefix("wiki/"),
        summary=summary,
        body_markdown=body,
        citations=citations,
        revision=1,
        created_at="2026-07-18T00:00:00Z",
        updated_at="2026-07-18T00:00:00Z",
    )


def _question(question: str, answer: str) -> dict[str, object]:
    return {"question": question, "answer": answer, "citations": ["S1-C1", "S2-C1"]}


def _mainline(stage: int, title: str, explanation: str, concepts: list[str]) -> dict[str, object]:
    return {
        "title": title,
        "explanation": explanation,
        "learning_outcome": explanation,
        "module_stage": stage,
        "concept_names": concepts,
        "citations": ["S1-C1", "S2-C1"],
    }


def _module(stage: int, title: str, concept: str, citation: str) -> LearningModule:
    return LearningModule(
        id=stage,
        project_id=0,
        stage=stage,
        title=title,
        stage_overview=f"第 {stage} 阶段从 {concept} 进入 Agent Harness 的工程实践。",
        core_explanation=(
            "本章把抽象原则落到可验证的系统边界：明确输入、工具、状态和成功条件，"
            "再通过 Trace 观察实际行为，而不是仅根据最终自然语言答案判断正确性。"
        ),
        knowledge_blocks=[
            {"title": f"{concept} 的工程边界", "body": "先定义可观测输入与输出，再允许模型在有限选择空间内作出判断。", "citations": [citation]},
            {"title": "发布前验证", "body": "每项能力都应有失败样例、成本预算和可回归的评测任务。", "citations": ["S2-C1"]},
        ],
        examples=[
            {"title": "受限工具调用", "body": "排障 Agent 先读取服务状态，再依据 contract 选择只读诊断工具；没有足够证据时停止而不是猜测。", "citations": [citation]},
        ],
        misconceptions=[
            {"title": "模型能调用工具就已经可靠", "misconception": "工具调用成功不代表任务正确。", "correction": "还需要权限、输入 schema、Trace 与结果 verifier 共同约束。", "citations": ["S1-C1", "S2-C1"]},
        ],
        further_reading=[
            {"title": "公开来源目录", "locator": "/demo#sources", "citations": [citation]},
        ],
        objectives=[f"解释 {concept} 在 Harness 中的作用", "为一个 Agent 步骤写出可观察的成功标准"],
        readings=[],
        key_concepts=[concept, "Trace", "Evaluation"],
        check_questions=[f"{concept} 如何限制不确定性？", "什么证据可以证明该步骤完成？"],
        practice_task="为一个两步工具任务写出输入、失败语义、终止条件和一条 Trace 断言。",
        citations=[citation, "S2-C1"],
    )
