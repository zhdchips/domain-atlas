# Domain Atlas MVP Regression Fixture

Domain Atlas 是一个 agentic domain learning system，用来帮助学习者快速进入一个新领域。它不是普通聊天机器人，也不是只把资料切块后检索的普通 RAG。系统的目标是从权威资料中摄取知识，生成可阅读、可维护、可引用的领域 Wiki，并在此基础上生成学习路线和支持可溯源问答。

## 核心对象

DomainProject 表示一个领域学习项目。它至少包含领域名称、学习目标、学习者水平、语言和交互模式。语言字段用于让同一套工作流支持中文优先和未来的英文切换。交互模式可以是 guided，也可以是 expert。guided 模式适合一键构建领域地图，expert 模式适合用户手动筛选资料并逐步构建。

Source 表示被系统采纳的资料。Source 可以来自 URL、Markdown 或 PDF。每个 Source 都应该保存 locator、title、source_type、raw_path、normalized_path、checksum 和 metadata。Source 的职责是保留资料来源和摄取状态，而不是承载模型生成的总结。

Chunk 是从 Source 中切分出来的证据片段。每个 Chunk 都需要稳定的 chunk_uid、ordinal、text 和 citation_label。citation_label 形如 S1-C1，用于把 Wiki 页面、学习路线和问答答案追溯回原始资料。

WikiPage 是领域 Wiki 的页面。Domain Atlas 的 Wiki 应该像 LLM Wiki 工作区，而不是一篇长报告。工作区中应包含 wiki/index、wiki/log、wiki/sources、wiki/concepts、wiki/entities、wiki/synthesis、wiki/templates 等分区。index 是入口目录，log 记录构建过程，sources 保存资料摘要，concepts 保存百科式概念页，synthesis 保存跨资料综合。

WikiSection 是 WikiPage 的可检索段落。每个 section 应该保留 heading、body_markdown、citations、source_chunk_uids、source_citation_labels 和 links。QA 优先检索 WikiSection，因为 Wiki 是系统整理后的知识层；当 Wiki 不足时，系统才退回原始 Chunk。

LearningGuide 表示领域学习的总导览，负责回答是什么、为什么存在、如何工作、组成、方法分支、代表组织、经典案例、最佳实践、失败误区和未来趋势。它还应该给出领域主线、核心概念、支线拓展和细节深化。

LearningModule 表示学习路线中的一个教材章节阶段。MVP 的学习路线固定生成五个阶段：入门认知、核心概念、关键方法、实践应用、进阶专题。每个阶段都应该包含 stage_overview、core_explanation、knowledge_blocks、examples、misconceptions、key_concepts、check_questions、practice_task、further_reading 和 citations。权威资料是 evidence，不是 curriculum；模块正文应该由 Agent 从资料中提取、综合和组织，阅读来源只作为 citation、provenance 和深入阅读入口。

## 构建流程

一键构建领域地图包含四个主要步骤。第一步是发现或接收资料。第二步是摄取资料，把 URL、Markdown 或 PDF 归一化成文本并切分成 Chunk。第三步是知识构建，LLM 根据带 citation 的 Chunk 生成 source_profiles、concepts、concept_edges、learning_guide、少量策展 Wiki 页面和 lesson-style learning_modules。第四步是持久化与向量化，系统把 Wiki 页面、WikiSection、概念、学习导览、学习模块写入 SQLite，并把 Chunk 与 WikiSection 写入向量索引。

为了降低 LLM 输出的不稳定性，系统不应该要求模型直接生成所有 Wiki 工作区页面。模型只负责抽取与综合。index、log、source pages、concept pages 和 template pages 应由代码确定性生成。这样可以减少 JSON 输出体积，也能保证 Wiki 工作区结构稳定。

## Provenance 规则

Domain Atlas 的所有核心输出都需要 provenance。Source profile 的 citations 必须指向 Chunk。Concept 的 definition 必须有 citations。WikiSection 应同时保存面向读者的 citations 和面向系统的 source_chunk_uids。QA 答案必须只使用检索到的 WikiSection 或 Chunk，并返回 citations 与 evidence_status。如果证据不足，答案应该明确说明当前知识库信息不足，而不是编造。

## 回归测试目标

固定真实 E2E 用例需要覆盖真实 LLM、真实 embedding、真实 SQLite、真实 Chroma 和真实 FastAPI route。它不需要依赖联网搜索，因为搜索结果会变化。它应该使用这份固定 Markdown 作为权威资料，上传为项目资料，执行摄取、构建、Wiki 展示、学习路线展示和 QA。成功标准包括：项目构建完成，至少生成 index、log、source、concept、synthesis、template 页面，生成 learning_guide，生成五个教材章节式学习模块，生成多个概念，WikiSection 已写入向量索引，并且 QA 能返回带 citation 的回答。
