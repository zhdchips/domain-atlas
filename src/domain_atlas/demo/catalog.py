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
    accessed_on: str
    authority_note: str
    evidence_locator: str


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

    @property
    def citation_links(self) -> dict[str, str]:
        links = {
            citation: source.evidence_locator
            for source in self.sources
            for citation in source.citations
        }
        links.update(
            {
                f"W:{page.slug}#1": f"/demo/wiki/{page.path.removeprefix('wiki/')}"
                for page in self.pages
            }
        )
        return links

    @property
    def evaluation_summary(self) -> dict[str, object]:
        return {
            "manifest_version": "golden-demo-evaluation/v1",
            "score": "25 / 25",
            "provider_calls": 0,
            "scope": "固定 Demo catalog 的结构与证据完整性检查",
            "limitation": "不是模型、RAG 或生产准确率指标。",
        }


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
            coverage="Agent loop、function tools、guardrails、handoff、session 与 tracing 的运行时接口。",
            citations=["S1-C1"],
            accessed_on="2026-07-18",
            authority_note="OpenAI 发布的 Agents SDK 一手技术文档，用于接口和运行时能力事实。",
            evidence_locator="https://openai.github.io/openai-agents-python/#why-use-the-agents-sdk",
        ),
        DemoSource(
            title="LangGraph overview",
            publisher="LangChain",
            url="https://docs.langchain.com/oss/python/langgraph/overview",
            source_type="official_docs",
            coverage="持久化、可恢复执行、人类介入、状态编排与可观测性基础设施。",
            citations=["S2-C1"],
            accessed_on="2026-07-18",
            authority_note="LangChain 发布的 LangGraph 一手文档，用于状态化编排和恢复能力事实。",
            evidence_locator="https://docs.langchain.com/oss/python/langgraph/overview#core-benefits",
        ),
        DemoSource(
            title="Building effective agents",
            publisher="Anthropic",
            url="https://www.anthropic.com/engineering/building-effective-agents",
            source_type="engineering_article",
            coverage="workflow 与 agent 的架构差异、何时增加自治性、工具设计和评测驱动迭代。",
            citations=["S3-C1"],
            accessed_on="2026-07-18",
            authority_note="Anthropic 工程团队发布的一手实践文章，用于工程取舍和常见模式。",
            evidence_locator="https://www.anthropic.com/engineering/building-effective-agents#when-and-when-not-to-use-agents",
        ),
        DemoSource(
            title="Effective harnesses for long-running agents",
            publisher="Anthropic",
            url="https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents",
            source_type="engineering_article",
            coverage="跨上下文窗口的进度记录、特性清单、增量提交、端到端测试和长任务失败模式。",
            citations=["S4-C1"],
            accessed_on="2026-07-18",
            authority_note="Anthropic 工程团队发布的长任务 Harness 复盘，包含明确失败案例与改进措施。",
            evidence_locator="https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents#the-long-running-agent-problem",
        ),
    ]
    pages = [
        _page(
            page_id=1,
            slug="index",
            page_type="index",
            path="wiki/index",
            title="Harness Map",
            summary="Agent Harness 是将模型、工具、状态、证据与评测组织为受控执行环境的工程层。",
            body=(
                "# Harness Map\n\n"
                "Harness 不等于更长的 prompt。它规定一个任务如何携带状态、调用受限工具、记录运行事实，"
                "并在失败时停止、恢复或请求人工判断。模型处理局部决策；系统负责权限、预算和可验证性。"
                "[S1-C1][S2-C1]\n\n"
                "学习顺序：先理解 [[Agent Loop]]，再定义 [[Tool Contracts]]；随后处理 [[Durable State]]，"
                "最后用 [[Trace and Evaluation]] 把行为变成可迭代的证据。"
            ),
            citations=["S1-C1", "S2-C1"],
        ),
        _page(
            page_id=2,
            slug="build-log",
            page_type="log",
            path="wiki/log",
            title="Demo Build Log",
            summary="黄金 Demo 的内容边界、来源范围和评测口径。",
            body=(
                "# Demo Build Log\n\n"
                "本 Demo 只采用四条公开一手资料。内容先依据资料覆盖范围写成 Wiki 与课程，"
                "再用版本化的 25 条确定性断言检查来源、引用、路线和 QA。评分只说明这个固定 catalog "
                "是否完整，不表示任意模型或任意领域的质量。[S3-C1][S4-C1]"
            ),
            citations=["S3-C1", "S4-C1"],
        ),
        _page(
            page_id=3,
            slug="evidence-map",
            page_type="source",
            path="wiki/sources/evidence-map",
            title="Evidence Map",
            summary="把每类学习断言映射到可点击的一手来源。",
            body=(
                "# Evidence Map\n\n"
                "S1 支撑 Agent loop、工具、guardrail 与 tracing 的 SDK 层事实；S2 支撑持久化、"
                "中断和状态化编排；S3 支撑 workflow/agent 取舍与工具设计建议；S4 提供长任务中"
                "一次性完成、遗失进度和过早宣告完成等失败模式。每个 citation label 都可回到来源。"
                "[S1-C1][S2-C1][S3-C1][S4-C1]"
            ),
            citations=["S1-C1", "S2-C1", "S3-C1", "S4-C1"],
        ),
        _page(
            page_id=4,
            slug="agent-loop",
            page_type="concept",
            path="wiki/concepts/agent-loop",
            title="Agent Loop",
            summary="在有限轮次中执行计划、调用工具、读取环境反馈并决定终止或继续。",
            body=(
                "# Agent Loop\n\n"
                "一个可靠 loop 的最小事实链是：目标和约束 -> 工具调用 -> 环境观察 -> 下一步判断。"
                "它不能只根据模型自述判断成功，而要读取工具结果或测试结果。loop 还必须有最大轮数、"
                "超时、预算和人工阻断点，以免开放式任务无限扩张。[S1-C1][S3-C1]"
            ),
            citations=["S1-C1", "S3-C1"],
        ),
        _page(
            page_id=5,
            slug="tool-contracts",
            page_type="concept",
            path="wiki/concepts/tool-contracts",
            title="Tool Contracts",
            summary="把工具的 schema、权限、超时、副作用与失败语义变成模型和系统共享的约束。",
            body=(
                "# Tool Contracts\n\n"
                "工具不是给模型的一段自由文本。一个 contract 至少要说明输入 schema、返回事实、"
                "可调用权限、超时和错误类型。清晰的 contract 让 planner 的选择、executor 的调用和 "
                "verifier 的判断能依据同一份事实，并能通过测试暴露误用。[S1-C1][S3-C1]"
            ),
            citations=["S1-C1", "S3-C1"],
        ),
        _page(
            page_id=6,
            slug="durable-state",
            page_type="concept",
            path="wiki/concepts/durable-state",
            title="Durable State",
            summary="跨步骤和跨会话保存足够的任务事实，使中断后的执行可以恢复而不必猜测历史。",
            body=(
                "# Durable State\n\n"
                "长任务会跨越请求、上下文窗口和失败边界。可恢复状态应保存当前目标、已完成工作、"
                "待办、关键证据与终止原因；它不是无限记录对话。缺少这些工件时，后续 agent 往往"
                "重复工作、丢失半成品，或错误宣告任务已经完成。[S2-C1][S4-C1]"
            ),
            citations=["S2-C1", "S4-C1"],
        ),
        _page(
            page_id=7,
            slug="evaluation-trace",
            page_type="synthesis",
            path="wiki/synthesis/evaluation-trace",
            title="Trace and Evaluation",
            summary="Trace 解释一次运行发生了什么；Evaluation 判断这些行为是否持续满足任务目标。",
            body=(
                "# Trace and Evaluation\n\n"
                "Trace 记录输入、状态转换、工具调用、耗时、重试和证据，因此可定位一次失败。"
                "Evaluation 使用版本化任务和明确门槛判断系统是否仍可发布。二者不能互相替代："
                "只有 Trace 没有标准，无法判断好坏；只有最终分数没有 Trace，无法定位原因。"
                "[S1-C1][S2-C1][S3-C1][S4-C1]"
            ),
            citations=["S1-C1", "S2-C1", "S3-C1", "S4-C1"],
        ),
    ]
    guide = LearningGuide(
        id=1,
        project_id=0,
        summary=(
            "Agent Harness Engineering 研究如何给模型驱动任务加上状态、工具边界、运行证据和"
            "评测门槛，使系统在复杂任务中仍可被观察、恢复和迭代。[S1-C1][S2-C1][S3-C1]"
        ),
        question_answers=[
            _question("是什么", "它是 Agent 的工程运行环境：定义 loop、工具 contract、状态、Trace 和评测，而不是单个模型或 prompt。", ["S1-C1", "S2-C1"]),
            _question("为什么存在", "模型输出本身不提供权限、预算、持久状态或可复现证据；Harness 以系统约束补齐这些能力。", ["S2-C1", "S4-C1"]),
            _question("如何工作", "系统让模型在受限 loop 中依据工具结果推进；每一步记录 Trace，并由停止条件、验证器或人工介入控制。", ["S1-C1", "S3-C1"]),
            _question("有哪些组成", "核心组成是目标与成功标准、工具 contract、状态与上下文、Trace、评测集、失败恢复和人工审批点。", ["S1-C1", "S2-C1"]),
            _question("有哪些流派/类型/方法论分支", "确定性 workflow 预定义路径；agent 由模型决定步骤和工具；多 agent 与人类介入是在边界清楚后才增加的扩展。", ["S3-C1", "S2-C1"]),
            _question("代表人物/组织/关键贡献者", "这个工程方向更适合按公开贡献组织理解：OpenAI 提供 SDK 原语，LangChain 提供状态图运行时，Anthropic 公开了 workflow、长任务 Harness 的工程复盘。", ["S1-C1", "S2-C1", "S3-C1", "S4-C1"]),
            _question("经典案例", "客服与编码任务具备工具、反馈和明确成功标准；长任务编码案例还暴露了跨会话进度管理和端到端验证的重要性。", ["S3-C1", "S4-C1"]),
            _question("最佳实践", "从简单可验证的 workflow 开始，明确工具语义与停止条件；把 Trace、版本化评测和失败样例作为发布前门槛。", ["S1-C1", "S3-C1", "S4-C1"]),
            _question("失败案例/常见误区", "典型失败包括试图一次完成大任务、后续会话不知道历史、未完成端到端测试就宣布完成，以及给工具过度自由的输入与权限。", ["S3-C1", "S4-C1"]),
            _question("未来趋势", "更成熟的系统会继续强化跨会话工件、可恢复状态、成本感知和评测驱动发布；是否需要多 agent 仍应由任务证据决定。", ["S2-C1", "S4-C1"]),
        ],
        mainline=[
            _mainline(1, "先判断是否真的需要 Agent", "从固定 workflow 与清晰成功标准开始，避免把复杂性当能力。", ["Agent Loop"], ["S3-C1"]),
            _mainline(2, "把工具变成可验证契约", "为输入、权限、返回事实、失败和超时写出明确边界。", ["Tool Contracts"], ["S1-C1", "S3-C1"]),
            _mainline(3, "让任务可恢复", "保存跨步骤所需的状态工件，而不是依赖模型记住一切。", ["Durable State"], ["S2-C1", "S4-C1"]),
            _mainline(4, "让运行过程可解释", "以 Trace 观察状态转换、工具结果、重试和停止原因。", ["Agent Loop", "Trace and Evaluation"], ["S1-C1", "S2-C1"]),
            _mainline(5, "用评测决定是否发布", "通过版本化任务、失败样例与门槛，判断改动是否真的提升系统。", ["Trace and Evaluation"], ["S3-C1", "S4-C1"]),
        ],
        core_concepts=[
            {"name": "Agent Loop", "explanation": "在环境反馈中推进任务的有限循环。", "depends_on": ["Tool Contracts"], "citations": ["S1-C1", "S3-C1"]},
            {"name": "Tool Contracts", "explanation": "工具 schema、权限和失败语义的显式协议。", "depends_on": [], "citations": ["S1-C1", "S3-C1"]},
            {"name": "Durable State", "explanation": "跨会话恢复任务所需的目标、进度、证据与终止事实。", "depends_on": ["Tool Contracts"], "citations": ["S2-C1", "S4-C1"]},
            {"name": "Trace and Evaluation", "explanation": "用运行事实定位问题，用版本化任务判断是否达标。", "depends_on": ["Agent Loop", "Durable State"], "citations": ["S1-C1", "S2-C1", "S4-C1"]},
        ],
        branches=[
            {"name": "Human-in-the-loop", "description": "对有外部副作用或证据不足的动作设置审批点，让人修改状态或终止执行。", "when_to_study": "工具会改变外部系统时。", "citations": ["S1-C1", "S2-C1"]},
            {"name": "Multi-agent", "description": "当角色边界、上下文隔离或并行任务能被清楚定义时，再用协调协议分配责任。", "when_to_study": "单一受控 loop 已能被评测后。", "citations": ["S2-C1", "S4-C1"]},
        ],
        details=[
            {"title": "预算与停止条件", "description": "为单次工具、整个任务和重试次数定义上限，防止成本与错误在 loop 中累积。", "practice_or_example": "记录每次终止是成功、预算耗尽、证据不足还是需要审批。", "citations": ["S1-C1", "S3-C1"]},
            {"title": "跨会话进度工件", "description": "保存特性清单、进度记录和可复现的 git 状态，使新会话能从真实事实继续。", "practice_or_example": "在每个阶段结束时更新待办、运行结果和恢复入口。", "citations": ["S4-C1"]},
        ],
        citations=["S1-C1", "S2-C1", "S3-C1", "S4-C1"],
        created_at="2026-07-18T00:00:00Z",
    )
    modules = [
        _module(
            1,
            "何时需要 Harness，而不是更长的 prompt",
            "Agent Loop",
            ["S3-C1"],
            "先区分可预测任务和开放式任务。若步骤、工具和成功标准可以预先写清，确定性 workflow 通常更便宜、更容易测试；只有工具选择或任务分解必须由模型根据环境反馈决定时，才需要把 loop 的控制权部分交给模型。Harness 的作用是让这种自治仍受预算、停止条件和验证约束。",
            [
                ("选择复杂度", "用任务的不确定性和可验证性判断是否需要 agent，而不是先选框架。"),
                ("成功标准", "在实现前写出可观察的成功、失败和需要人工介入的信号。"),
            ],
            ("案例：固定排障流程", "已知要检查的服务、日志和阈值时，用 workflow 固定顺序执行；不要让模型自由猜测下一步。"),
            ("误区：有工具调用就必须叫 Agent", "工具调用可以属于 workflow；关键区别是路径是否由预定义代码控制。"),
            ["什么任务特征证明固定 workflow 足够？", "为什么高成本或高副作用任务应先定义停止条件？"],
            "为一个业务任务写出固定 workflow 与有限自治 loop 两个版本，并说明选择依据和失败边界。",
        ),
        _module(
            2,
            "把工具变成可验证的 contract",
            "Tool Contracts",
            ["S1-C1", "S3-C1"],
            "Agent 能否可靠使用工具，取决于工具接口是否把不确定性压缩到可管理范围。contract 不只描述参数，还要写清授权范围、返回的是事实还是建议、超时与重试语义、是否产生副作用，以及调用失败后模型能安全采取什么动作。这样 verifier 才能根据工具输出而非模型自述检查结果。",
            [
                ("输入与权限", "使用结构化 schema，区分只读诊断、受审批写入和禁止调用的工具。"),
                ("失败语义", "把可重试网络失败、权限不足、参数错误和证据不足拆开返回。"),
            ],
            ("案例：只读排障工具", "工具返回服务状态、时间戳和错误码；Agent 在没有足够证据时停止并请求人工确认。"),
            ("误区：自然语言描述够用了", "模糊描述会使模型难以区分相似工具，也让测试无法定位错误输入。"),
            ["一个安全 contract 最少要写出哪些字段？", "为什么工具成功返回不等于业务任务成功？"],
            "为一个会修改外部记录的工具定义 schema、权限、审批点、超时和四类失败返回。",
        ),
        _module(
            3,
            "让长任务跨会话继续而不猜测历史",
            "Durable State",
            ["S2-C1", "S4-C1"],
            "长任务不会一直停留在同一上下文窗口。要恢复执行，系统需要保存目标、已验证的进度、未完成特性、关键证据、当前预算和终止原因。有效状态是下一次执行可直接读取的工件，不是无限堆积对话；它还应保留恢复入口和最近验证结果，并告诉后续 agent 下一件最小可验证工作是什么。",
            [
                ("恢复最小集", "保存目标、当前阶段、已通过验证、待办和阻塞原因，使恢复不依赖模型猜测。"),
                ("干净交接", "每轮结束前留下可运行状态、进度记录和描述性提交，避免半完成特性污染下一轮。"),
            ],
            ("案例：多会话编码", "初始化阶段创建特性清单和进度日志；后续会话先读状态与测试，再只完成一项特性。"),
            ("误区：上下文压缩等于可靠记忆", "压缩可能丢失任务边界；恢复仍应依赖结构化的外部状态工件。"),
            ["哪些事实必须跨会话保存？", "为什么每轮只完成一项可验证工作能降低长期任务风险？"],
            "为一个三会话任务设计状态 schema，并模拟第二会话如何从失败后恢复。",
        ),
        _module(
            4,
            "用 Trace 把行为变成可解释证据",
            "Trace and Evaluation",
            ["S1-C1", "S2-C1"],
            "最终答案正确并不说明过程可靠。Trace 应串联输入、模型决策、工具调用、状态变化、重试、耗时和终止原因，帮助工程师判断错误来自检索、工具、编排还是模型判断。可观测性还要求在 Trace 中避免记录不必要的敏感内容，并为每类失败保留可统计的事件。",
            [
                ("最小 Trace", "至少关联任务 ID、步骤、工具输入摘要、结果状态、耗时、重试和终止原因。"),
                ("诊断闭环", "用 Trace 找到具体失败节点，再把该节点转成可重复的评测样例。"),
            ],
            ("案例：检索问答", "答案引用不足时，Trace 应显示召回的 Wiki/Chunk、证据判断和拒答原因，而不是只记录空答案。"),
            ("误区：只记录最终回答", "没有中间状态无法判断是模型幻觉、工具错误还是编排遗漏。"),
            ["Trace 与日志有什么不同？", "一次证据不足的 QA 应记录哪些运行事实？"],
            "为一个两步 Agent 执行设计 Trace 事件，并写出依据这些事件定位失败的查询。",
        ),
        _module(
            5,
            "让评测成为发布门槛，而不是演示装饰",
            "Trace and Evaluation",
            ["S3-C1", "S4-C1"],
            "评测把“看起来可用”转换为版本化的通过条件。先选真实任务与失败样例，再为答案证据、工具行为、停止条件、成本和端到端体验设定可解释断言。每次改动都回放相同集合；失败时回到 Trace 定位根因。复杂编排只有在能证明收益超过成本和延迟时才值得保留。",
            [
                ("确定性门禁", "对引用存在性、schema、路由、安全边界和预期拒答使用稳定规则。"),
                ("质量审阅", "对教学清晰度与来源取舍保留人工 rubric，不用单个 LLM judge 替代责任。"),
            ],
            ("案例：本 Demo", "25 条离线断言检查来源、Wiki、课程、QA 与导航；评分明确不代表通用模型能力。"),
            ("误区：100% 就代表产品准确率", "固定 fixture 只能说明该 fixture 满足既定不变量；泛化能力需要独立数据与持续评测。"),
            ["哪些指标适合确定性评测，哪些必须人工审阅？", "为什么要把失败样例纳入发布门槛？"],
            "为一个 Agent 功能写出五条确定性断言、一条人工审阅项和一条会导致拒绝发布的失败样例。",
        ),
    ]
    qa_records = [
        _qa(1, "为什么 Agent Harness 不等于一个更长的 prompt？", "Prompt 只能影响一次生成；Harness 还定义状态如何保存、工具如何被限制、失败如何恢复，以及结果如何被 Trace 和评测验证。因此它提供的是运行时治理边界，而不只是文本指令。", ["W:agent-loop#1", "W:evaluation-trace#1"], ["S1-C1", "S2-C1"]),
        _qa(2, "什么时候应先用 workflow，而不是增加 Agent 自主性？", "当任务步骤、工具选择和成功标准可以预先定义时，应先采用确定性 workflow。只有任务确实需要模型依据环境反馈决定下一步，并且预算、停止条件和验证已存在时，才逐步增加自治性。", ["W:agent-loop#1", "W:tool-contracts#1"], ["S3-C1"]),
        _qa(3, "长任务恢复时，最应该保存哪些状态？", "应保存当前目标、已验证进度、未完成工作、关键证据、预算和终止/阻塞原因。这样新会话能从事实继续，而不是根据压缩后的对话猜测历史。", ["W:durable-state#1"], ["S2-C1", "S4-C1"]),
        _qa(4, "Trace 和 Evaluation 的职责有什么区别？", "Trace 记录一次执行发生了什么，帮助定位工具、状态或编排中的失败；Evaluation 用版本化任务和门槛判断系统是否持续满足目标。前者解释过程，后者判断是否达标。", ["W:evaluation-trace#1"], ["S1-C1", "S2-C1", "S3-C1"]),
        QARecord(
            id=5,
            project_id=0,
            question="所有 Agent 的工具调用超时应该统一设为多少秒？",
            answer="当前资料无法支持一个适用于所有 Agent 和工具的统一秒数。超时应结合工具性质、用户等待预期、重试策略、成本预算和是否存在副作用来设计；需要在具体系统的 Trace 与评测中验证。",
            citations=[],
            source_provenance=[],
            evidence_status="insufficient",
            created_at="2026-07-18T00:00:00Z",
        ),
    ]
    return PublicDemoCatalog(project, sources, pages, guide, modules, qa_records)


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


def _question(question: str, answer: str, citations: list[str]) -> dict[str, object]:
    return {"question": question, "answer": f"{answer}[{']['.join(citations)}]", "citations": citations}


def _mainline(
    stage: int, title: str, explanation: str, concepts: list[str], citations: list[str]
) -> dict[str, object]:
    return {
        "title": title,
        "explanation": explanation,
        "learning_outcome": explanation,
        "module_stage": stage,
        "concept_names": concepts,
        "citations": citations,
    }


def _module(
    stage: int,
    title: str,
    concept: str,
    citations: list[str],
    explanation: str,
    blocks: list[tuple[str, str]],
    example: tuple[str, str],
    misconception: tuple[str, str],
    questions: list[str],
    practice_task: str,
) -> LearningModule:
    return LearningModule(
        id=stage,
        project_id=0,
        stage=stage,
        title=title,
        stage_overview=f"第 {stage} 阶段围绕 {concept} 建立一个可验证的工程判断。",
        core_explanation=explanation,
        knowledge_blocks=[{"title": title, "body": body, "citations": citations} for title, body in blocks],
        examples=[{"title": example[0], "body": example[1], "citations": citations}],
        misconceptions=[{"title": misconception[0], "misconception": misconception[0], "correction": misconception[1], "citations": citations}],
        further_reading=[{"title": "查看原始证据", "locator": "/demo#sources", "citations": citations}],
        objectives=[f"解释 {concept} 在 Harness 中如何降低不确定性", "为这一阶段写出一个可观察的成功条件"],
        readings=[],
        key_concepts=[concept, "Trace", "Evaluation"],
        check_questions=questions,
        practice_task=practice_task,
        citations=citations,
    )


def _qa(
    record_id: int, question: str, answer: str, citations: list[str], source_provenance: list[str]
) -> QARecord:
    return QARecord(
        id=record_id,
        project_id=0,
        question=question,
        answer=answer,
        citations=citations,
        source_provenance=source_provenance,
        evidence_status="supported",
        created_at="2026-07-18T00:00:00Z",
    )
