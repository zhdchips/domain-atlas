# 用三个断点读懂 Domain Atlas

这份文档面向第一次阅读 Domain Atlas 源码的人。目标不是解释每个模块，而是沿三个 POST 入口看清系统如何把一个领域名称转化为可检索、可学习、可溯源的知识库。

建议按以下顺序调试：

1. `POST /domains`：项目和学习边界从哪里产生。
2. `POST /domains/{project_id}/autopilot`：证据如何变成 Wiki 与学习路线。
3. `POST /domains/{project_id}/qa`：问题如何沿 Wiki 回溯到原始证据。

## 先建立全局心智模型

```text
领域名称、目标和水平
        |
        v
DomainProject + Intake 边界
        |
        v
SourceCandidate -> Source -> Chunk
                              |
                              v
                 WikiPage -> WikiSection
                              |
                              +-> LearningGuide / LearningModule
                              |
                              v
                       Wiki-first QA
```

## 仓库地图

先把仓库分成四个区域：产品源码、测试与工具、设计文档、运行产物。阅读三个主流程时，主要停留在 `src/domain_atlas/`，遇到行为不确定时再去 `tests/` 找对应例子。

```text
domain-atlas/
├── src/domain_atlas/       产品源码
├── tests/                  单元、集成和确定性 E2E
├── scripts/                回归、真实 E2E、评测与截图脚本
├── specs/                  历次 SDD 的需求、设计和任务
├── docs/                   使用、部署和源码阅读文档
├── evals/                  版本化评测用例
├── reports/                评测结果
├── data/                   本地运行数据
├── .github/                GitHub Actions CI
├── pyproject.toml          Python 依赖、入口和测试配置
├── Dockerfile              容器镜像
├── render.yaml             公开只读 Demo 部署
└── render.private.yaml     私有 Owner 实例部署
```

### 产品源码

```text
src/domain_atlas/
├── web/          HTTP 路由、认证依赖、Jinja 模板和静态资源
├── workflow/     Autopilot、知识构建和后台任务编排
├── intake/       项目输入评估、歧义判断和范围澄清
├── discovery/    Exa 搜索与候选资料发现
├── ingestion/    URL/PDF/Markdown 加载、质量检查、切片和向量化
├── qa/           Wiki-first 与原始 Chunk 兜底问答
├── domain/       领域模型和 SQLite Repository
├── providers/    LLM、Embedding 和 Chroma 适配器
├── wiki/         Wiki Markdown 渲染、内部链接和结构检查
├── auth/         GitHub OAuth、Session 与 CSRF 所需状态
├── core/         配置、数据库、持久化、备份和 Provider 重试
├── demo/         公开只读黄金 Demo 数据
├── evaluation/   黄金 Demo 评测逻辑
└── cli.py        启动、备份、恢复和 Session 撤销命令入口
```

可以用一条简单规则判断应该去哪个目录：

| 想找什么 | 先看哪里 |
| --- | --- |
| 请求从哪里进入 | `web/` |
| 多步骤业务如何编排 | `workflow/` 或 `qa/` |
| 数据如何读写 SQLite | `domain/` |
| 外部 API 或向量库如何调用 | `providers/`、`discovery/` |
| 文件如何变成可引用证据 | `ingestion/` |
| 配置、备份和可靠性机制 | `core/` |

三个主流程在目录间的移动路径是：

```text
创建项目：web -> intake -> domain

一键构建：web -> workflow -> discovery -> ingestion
                   |                         |
                   +------ providers -------+
                   |
                   +-> domain

引用问答：web -> qa -> providers/vector_index -> domain
```

### 测试、脚本和 SDD

- `tests/` 描述模块的输入、输出和失败边界，通常是理解陌生函数最快的入口。
- `scripts/` 负责运行分层回归、真实 Provider E2E 和浏览器检查，不承载线上业务逻辑。
- `specs/` 保存每轮 SDD 的决策背景。需要理解“为什么这样设计”时看这里，不必在第一次读代码时逐份阅读。
- `evals/` 保存固定评测题，`reports/` 保存评测结果；它们不参与普通请求处理。

### 运行目录与编辑器目录

以下目录不是产品源码，第一次阅读时可以折叠：

```text
.venv/          本地 Python 虚拟环境
.pytest_cache/  Pytest 缓存
__pycache__/    Python 字节码缓存
.idea/          JetBrains 编辑器配置
.vscode/        VS Code 调试和工作区配置
data/           本地 SQLite、Chroma、资料文件和锁文件
```

其中 `data/` 很重要，但它是运行结果而不是实现。调试数据问题时再展开；阅读控制流时先从 `src/domain_atlas/` 开始。仓库中的空 `evaluations/` 目录当前也不参与系统运行。

系统有三类存储，各自职责不同：

| 存储 | 主要内容 | 角色 |
| --- | --- | --- |
| SQLite | 项目、候选资料、Source、Chunk、Workflow、Wiki、课程、QA 记录 | 业务状态的事实来源 |
| Chroma | Chunk 与 Wiki Section 的向量索引 | 可重建的检索索引 |
| `DATA_DIR` | URL/Markdown/PDF 的原始文件、标准化文本和备份 | 原始资料与持久化文件 |

应用装配入口是 [`create_app`](../src/domain_atlas/web/app.py)。它根据配置创建 Repository、Provider、Workflow 和 Router。三个 POST 路由都挂在 `private_write_router` 上，因此在进入断点前已经完成 Owner 身份、CSRF 和数据目录锁检查；本地模式使用本地 Owner Session，公开 Demo 则不会暴露这些写入口。

## 主流程一：创建项目

### 入口断点

文件：[`src/domain_atlas/web/app.py`](../src/domain_atlas/web/app.py)

函数：`create_domain`

```text
POST /domains
  -> fallback_intake_assessment
  -> _resolve_intake_assessment
  -> DomainProjectRepository.create
  -> 303 /domains/{id}/intake 或 /domains/{id}
```

### 跟踪顺序

1. 表单提交 `name`、`goal`、`level`、`language` 和 `interaction_mode`。
2. `fallback_intake_assessment` 先生成确定性的本地判断，保证 LLM 不可用时仍能创建项目。
3. `_resolve_intake_assessment` 尝试调用 `LLMIntakeAssessmentProvider`。只有返回结构合法且置信度达到阈值时，模型判断才会生效；否则保留本地判断。
4. `assessment.needs_clarification` 决定项目是否先进入澄清页。
5. [`DomainProjectRepository.create`](../src/domain_atlas/domain/projects.py) 将项目和 Intake 元数据写入 `domain_projects`。
6. 路由使用 303 重定向：需要澄清时进入 `/intake`，边界清晰时直接进入项目页。

这里有一个重要设计：**项目会先创建，再澄清**。因此澄清状态、推荐范围和用户最终选择都能持久化，而不是只存在于某次 HTTP 请求里。

### 值得观察的变量

| 变量 | 要回答的问题 |
| --- | --- |
| `fallback` | 没有 LLM 时系统会怎样理解输入？ |
| `assessment_source` | 本次采用了 `llm` 还是 `fallback`？ |
| `assessment_status` | LLM 是未配置、失败、无效还是低置信度？ |
| `assessment.default_scope` | 后续搜索真正使用的领域边界是什么？ |
| `project.intake_status` | 下一步是澄清还是直接构建？ |

### 该流程的产物

主要写入 `domain_projects`。后续所有资料、工作流、Wiki 和问答都通过 `project_id` 归属于这个项目。

## 主流程二：一键构建领域地图

### 入口断点

文件：[`src/domain_atlas/web/app.py`](../src/domain_atlas/web/app.py)

函数：`run_autopilot`

```text
POST /domains/{project_id}/autopilot
  -> BackgroundWorkflowRunner.submit
  -> 后台线程
  -> AutopilotWorkflow.run
       -> 搜索与资料策略
       -> 摄取与向量化
       -> KnowledgeBuildWorkflow.run
```

路由本身不执行搜索或 LLM 构建。它只创建一条持久化的 `guided_autopilot` Run，并启动本地后台线程，然后立即用 303 返回项目页。页面通过工作流状态接口读取 `workflow_runs` 和 `workflow_steps`，所以刷新页面不会丢失进度。

[`BackgroundWorkflowRunner`](../src/domain_atlas/workflow/background.py) 是当前单进程 MVP 的任务执行器：

- 每个项目同一时间只允许一个活动任务；
- Python daemon thread 执行耗时工作；
- SQLite 保存 queued、running、completed、failed 和 interrupted 状态；
- 服务重启后，旧进程遗留的活动任务会标记为 interrupted，可由用户显式重试。

它不是 Celery、Redis Worker，也不是 `asyncio` 任务队列。

### 第二个断点：编排主干

文件：[`src/domain_atlas/workflow/autopilot.py`](../src/domain_atlas/workflow/autopilot.py)

函数：`AutopilotWorkflow.run`

主流程可以压缩为四个阶段：

```text
Discover -> Select -> Ingest -> Build
```

#### 1. Discover：搜索候选

- 使用 `project.effective_scope` 搜索；它优先取用户确认后的 `scope`，没有时才退回项目名称。
- [`ExaSearchProvider`](../src/domain_atlas/discovery/exa.py) 返回 `SourceCandidateDraft`。
- [`build_selection_plan`](../src/domain_atlas/workflow/source_policy.py) 评估来源类型、权威性、来源族、地区和是否需要直接权威资料。
- 品牌或机构服务流程缺少一方资料时，流程会追加受限的官方与地区补搜，并检查官方入口。
- 候选及其判定结果写入 `source_candidates`，便于 UI 展示和事后解释。

#### 2. Select：形成可补位队列

Selection Plan 不只返回最终两条资料，而是生成按质量排序的候选队列。这样第一条 URL 遇到 403、超时或解析失败时，后面的候选可以继续补位。

如果候选没有通过当前领域的证据策略，流程在这里失败，不会带着薄弱资料继续生成 Wiki。

#### 3. Ingest：把资料变成证据层

每个被接受的候选先转换为 `Source`，再交给 [`IngestionService.ingest_source`](../src/domain_atlas/ingestion/service.py)：

```text
URL / Markdown / PDF
  -> Loader 抓取或读取
  -> 保存 raw 与 normalized 文件
  -> 内容质量和近重复检查
  -> 切分 Chunk，生成 S1-C1 形式的稳定引用
  -> Embedding
  -> Chroma Chunk 索引
```

Autopilot 不以“成功抓取两条 URL”为门槛，而以“成功摄取两个独立来源族”为门槛。相同来源族的重复页面不会被当成两份独立证据。默认满足门槛后就停止继续摄取，减少时间和 Provider 成本。

这一阶段的关键数据关系是：

```text
source_candidates.id
        |
        v
sources.metadata.candidate_id
        |
        v
chunks.source_id + chunks.citation_label
```

#### 4. Build：把证据编译成学习层

只有来源门槛通过后，才调用 [`KnowledgeBuildWorkflow.run`](../src/domain_atlas/workflow/build.py)：

1. 从 SQLite 读取已摄取 Chunk，并编译带 citation 的上下文。
2. 要求 LLM 返回结构化 JSON，而不是直接生成一个 Markdown 长文。
3. 校验 Wiki、概念和课程结构；课程结构不合格时允许一次定向修复。
4. 补齐 `index`、`log`、`sources`、`concepts`、`synthesis` 和 `templates` 等工作区页面。
5. 以一次替换操作写入项目的 Wiki、概念关系、学习指南和学习模块。
6. 将 Wiki 拆成 `WikiSection`，再次 Embedding，并写入独立的 Wiki Section 向量集合。

因此系统存在两层向量索引：

- Chunk 索引回答“原始资料里有什么”；
- Wiki Section 索引回答“系统已经如何组织这个领域”。

### 推荐断点

| 位置 | 观察重点 |
| --- | --- |
| `BackgroundWorkflowRunner.submit` | Run 如何入库，为什么请求立即返回 |
| `AutopilotWorkflow.run` | 四阶段的总状态机 |
| `build_selection_plan` | 为什么某条资料被接受、降级或拒绝 |
| `IngestionService.ingest_source` | Source 如何变成文件、Chunk 和向量 |
| `KnowledgeBuildWorkflow.run` | Chunk 如何变成 Wiki、课程和 Wiki 向量 |

### 失败时从哪里看

先看 `workflow_runs.status/error`，再按顺序查看 `workflow_steps`。每个阶段会保存稳定的步骤名和可展示输出；Provider 的有限重试也会记录为 `provider_retry`。这比只看最终异常更容易判断失败发生在搜索、策略、抓取、Embedding 还是 LLM 结构化输出。

## 主流程三：带引用问答

### 入口断点

文件：[`src/domain_atlas/web/app.py`](../src/domain_atlas/web/app.py)

函数：`ask_question`

```text
POST /domains/{project_id}/qa
  -> RetrievalQAService.answer
  -> QARepository.create
  -> 303 /domains/{project_id}/qa
```

与 Autopilot 不同，当前 QA 在 HTTP 请求内同步完成。完成后把结果写入 `qa_records`，再通过 303 回到 GET 页面，避免浏览器刷新时重复提交表单。

### 第二个断点：Wiki-first 检索

文件：[`src/domain_atlas/qa/service.py`](../src/domain_atlas/qa/service.py)

函数：`RetrievalQAService.answer`

```text
问题
  -> Question Embedding
  -> query_wiki_sections
       | 有召回
       v
     Wiki 回答 + W:<section_uid> 引用 + Source provenance

       | 零召回
       v
     query raw chunks
       | 有召回                         | 零召回
       v                                v
     Chunk 回答 + S1-C1 引用           明确拒答
```

需要特别注意：**原始 Chunk 兜底只在 Wiki Section 零召回时发生**。如果已经召回 Wiki，但模型判断这些 Wiki 证据不足，当前实现会直接拒答，不会再查询 Chunk。

### Wiki 分支

1. 从 Chroma 的项目 Wiki 集合召回最多 `top_k` 个 section。
2. Prompt 把 section 内容、`W:<section_uid>`、页面信息和原始 `source_citation_labels` 一起交给 LLM。
3. 模型返回 answer、citations 和 evidence_status。
4. 代码只保留本次召回集合中的 `W:` 引用，模型虚构的 Wiki 引用会被过滤。
5. `_source_provenance` 汇总这些 Wiki Section 背后的 `Sx-Cy`，形成从答案到原始资料的第二层溯源。

### Chunk 兜底分支

1. 从原始 Chunk 集合召回证据。
2. Prompt 只允许使用召回文本回答。
3. 代码只接受本次召回 Chunk 的 `Sx-Cy` 标签。
4. 没有有效回答、有效引用或 sufficient 状态时，统一写入证据不足的拒答记录。

### 最终记录

[`QARepository`](../src/domain_atlas/domain/qa.py) 将以下字段写入 `qa_records`：

| 字段 | 含义 |
| --- | --- |
| `answer` | 最终答案或证据不足提示 |
| `citations_json` | 直接支撑答案的 Wiki 或 Chunk 引用 |
| `source_provenance_json` | Wiki 引用背后的原始 Chunk 来源 |
| `evidence_status` | `sufficient` 或 `insufficient` |

## 三条流程如何连接

把三个断点串起来，Domain Atlas 的核心不是简单串联几个 LLM 调用，而是逐步建立可追踪的数据契约：

```text
POST /domains
  产出 project_id + effective_scope
              |
              v
POST /autopilot
  产出 Source/Chunk + Wiki/课程 + 两层向量索引
              |
              v
POST /qa
  消费 Wiki/Chunk 索引，产出带 citation/provenance 的 QARecord
```

`project_id` 是所有数据的归属边界，citation 是证据层与学习层之间的桥梁，Workflow Run 则是长任务的可观测外壳。

## 15 分钟阅读路线

如果只想快速建立代码感，可以按这个顺序单步执行：

1. 在 `create_domain` 停住，观察 `assessment` 和最终 `project`。
2. 在 `run_autopilot` 停住，确认 HTTP 层只调用 `task_runner.submit`。
3. 跳到 `AutopilotWorkflow.run`，只跟 `discover_candidates`、`ingest_sources`、`build_knowledge` 三个 step。
4. 在 `IngestionService.ingest_source` 看一条 URL 如何生成 Chunk 和 `S1-C1`。
5. 在 `KnowledgeBuildWorkflow.run` 看同一批 Chunk 如何生成 Wiki Section 并建立第二层索引。
6. 在 `RetrievalQAService.answer` 看问题先命中 Wiki，再检查 `citations` 与 `source_provenance`。

读完后，你应该能回答五个问题：

1. 为什么项目可能先进入澄清页？
2. 为什么一条 URL 抓取失败不会立刻终止 Autopilot？
3. 为什么至少需要两个独立来源族？
4. Wiki 和原始 Chunk 为什么要建立两套索引？
5. 系统如何阻止 LLM 返回无法溯源的引用？

## 对应测试

| 想验证的行为 | 测试入口 |
| --- | --- |
| 项目创建和 Web 路由 | [`tests/test_app.py`](../tests/test_app.py) |
| Intake 判定 | [`tests/test_intake_assessment.py`](../tests/test_intake_assessment.py) |
| Autopilot 选择、补位和证据门槛 | [`tests/test_autopilot.py`](../tests/test_autopilot.py) |
| URL/Markdown/PDF 摄取 | [`tests/test_ingestion.py`](../tests/test_ingestion.py) |
| Wiki 与课程构建 | [`tests/test_build_workflow.py`](../tests/test_build_workflow.py) |
| Wiki-first 与 Chunk 兜底问答 | [`tests/test_qa_service.py`](../tests/test_qa_service.py) |
| 三阶段确定性端到端流程 | [`tests/e2e/test_guided_domain_flow.py`](../tests/e2e/test_guided_domain_flow.py) |

建议先读测试名，再回到实现下断点。测试通常比 UI 更直接地展示一个模块的输入、输出和失败边界。
