# Domain Atlas

**一个可溯源的领域学习系统，将精选资料转化为 LLM Wiki、结构化学习路线和带引用的问答。**

Domain Atlas 不是通用聊天界面。它将证据与学习内容分层管理：原始资料切片保留来源信息；生成的 Wiki 页面负责组织领域知识；回答优先引用 Wiki，并仅在必要时回退到原始资料证据。

**[在线体验](https://domain-atlas-demo.onrender.com)** · [快速开始](#快速开始) · [系统架构](#系统架构)

> 在线演示部署于 Render Free，首次打开可能需要约 1 分钟唤醒。

<p align="center">
  <img src="docs/assets/demo-overview.png" alt="Domain Atlas 公开演示概览" width="49%" />
  <img src="docs/assets/demo-wiki.png" alt="Domain Atlas LLM Wiki 工作区" width="49%" />
</p>

<p align="center">
  <img src="docs/assets/demo-learning-path.png" alt="Domain Atlas 生成的学习路线" width="49%" />
  <img src="docs/assets/demo-cited-qa.png" alt="Domain Atlas 带引用的问答" width="49%" />
</p>

## 核心能力

- **发现并摄取证据**：搜索候选资料，或导入 URL、Markdown 和 PDF，同时保留完整的来源信息。
- **构建 LLM Wiki**：基于证据层生成百科式页面、概念链接、来源档案和可导航的知识工作区。
- **教学，而不只是检索**：创建分阶段的学习路线，包含知识讲解、知识块、示例、检查问题、实践任务和拓展阅读。
- **带引用回答**：以 Wiki 章节作为主要检索层，必要时回退到原始资料切片；证据不足时明确说明无法回答。
- **让失败清晰可见**：展示候选资料选择、权威性与地区判断、摄取进度、重试和恢复状态，不使用薄弱资料静默构建知识库。

## 系统架构

```mermaid
flowchart LR
    A[领域名称或学习者提供的资料] --> B[资料发现与候选选择策略]
    B --> C[资料摄取]
    C --> D[Source 与 Chunk 证据层]
    D --> E[LLM Wiki 与概念图谱]
    D --> F[学习路线]
    E --> G[Wiki 优先的引用问答]
    D --> G
    B --> H[工作流追踪与故障恢复]
    C --> H
```

`Source -> Chunk` 构成证据层，`Wiki page -> Wiki section` 构成学习层。稳定的引用标识连接两个层次，使学习者可以从 Agent 生成的讲解回溯到支撑它的原始资料。

## 交互模式

| 模式 | 适用流程 |
| --- | --- |
| 引导模式（Guided） | 从一个领域名称开始；Domain Atlas 自动搜索、评估候选资料、摄取可用证据，并构建 Wiki 和学习路线。涉及品牌服务流程时，必须具备直接证据或一方资料。 |
| 专家模式（Expert） | 搜索候选资料，由用户确认来源，再手动执行摄取和构建步骤。适合学习者已有偏好的资料集合，或需要覆盖自动推荐结果的情况。 |

资料可访问性会被视为证据质量的一部分，而不是隐藏的实现细节。遭到拦截的 URL、跨地区的官方网站、直接证据不足或无法访问的官方服务入口，都会连同来源信息和恢复路径一并展示。

## 快速开始

### 环境要求

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/zhdchips/domain-atlas.git
cd domain-atlas
cp .env.example .env
uv sync --extra dev
uv run uvicorn domain_atlas.web.app:create_app --factory --reload
```

打开 `http://127.0.0.1:8000`。

只有在使用真实搜索、内容生成或向量化服务时，才需要在 `.env` 中配置 Provider。支持的环境变量请参阅 [`.env.example`](.env.example)。

## 公开只读演示

确定性的作品集 Demo 可以安全地公开访问，因为它不会创建项目、接收文件上传、读取本地数据，也不会调用 Exa、LLM、Embedding 或 URL 抓取服务。

```bash
PUBLIC_DEMO_MODE=true uv run uvicorn domain_atlas.web.app:create_app --factory
```

打开 `http://127.0.0.1:8000/demo`。预构建的 `Agent Harness Engineering` 案例包含资料来源、Wiki 工作区、5 个学习模块、带引用的问答示例，以及包含 25 项检查的黄金评测集。

**在线 Demo：[https://domain-atlas-demo.onrender.com](https://domain-atlas-demo.onrender.com)**

## 私有单用户版本

供个人长期使用的可写实例采用 `private_owner` 模式：GitHub OAuth 只允许配置的唯一 numeric user ID，项目、SQLite、Chroma、上传资料和备份位于独立持久化磁盘。它与公开只读 Demo 分开部署，不共享数据或 Provider 凭证。

私有实例不能使用 Render Free 的临时文件系统。仓库提供独立的 [`render.private.yaml`](render.private.yaml)、数据目录启动校验、Session/CSRF 防护、中断任务重试，以及带 manifest/checksum 的备份恢复命令。完整步骤见[私有单用户部署指南](docs/private-deployment.md)。

## Docker

构建镜像：

```bash
docker build -t domain-atlas:local .
```

运行公开 Demo：

```bash
docker run --rm -p 8000:8000 \
  -e PUBLIC_DEMO_MODE=true \
  domain-atlas:local
```

运行本地可写实例时，请挂载 `/app/data`，并在运行时提供 Provider 配置：

```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --env-file .env \
  domain-atlas:local
```

可写模式仅适用于受信任的本地环境。它**不是**一个开箱即用的匿名 SaaS 部署方案：生产环境仍需补充身份认证、租户隔离、Provider 配额、访问限流、SSRF 防护和文件上传治理。

## Render 部署

根目录的 [`render.yaml`](render.yaml) 将只读 Demo 声明为 Singapore 区域的 Docker Web Service。首次发布时，在 Render Dashboard 中选择 **New → Blueprint** 并连接本仓库；Blueprint 不需要数据库、磁盘或任何 Provider Key，只会设置 `PUBLIC_DEMO_MODE=true`。

Render 会通过 `/health` 判断新版本是否可用，并在 GitHub CI 检查通过后自动部署当前默认分支。Free 实例空闲后可能休眠，首次访问可能需要约一分钟恢复；正式用于简历投递时，建议使用不会休眠的实例。

执行远程只读验证：

```bash
export DOMAIN_ATLAS_DEMO_URL="https://domain-atlas-demo.onrender.com"
uv run python scripts/smoke_public_demo_remote.py --base-url "$DOMAIN_ATLAS_DEMO_URL"
```

该探针只访问 Demo 自身，不访问 citation 外站，也不会提交可触发搜索、摄取、LLM 或 Embedding 的有效载荷。发布异常时，在 Render 的 Events 中回滚到最近一次健康部署，然后重新运行同一探针。

## 验证与测试

默认回归测试均为确定性测试，不会消耗 Provider 额度：

```bash
uv run python scripts/regression.py --fast
uv run python scripts/regression.py --e2e
uv run python scripts/regression.py --golden-demo-eval
uv run python scripts/regression.py --browser-e2e
```

浏览器层同时覆盖本地完整版本、公开只读 Demo，以及使用 Fake GitHub OAuth 的私有 owner 桌面/手机流程。

首次运行浏览器测试前，需要安装 Chromium：

```bash
uv run python -m playwright install chromium
```

真实 Provider 验证默认不执行，需要显式启用：

```bash
uv run python scripts/regression.py --live
uv run python scripts/regression.py --live-guided-e2e
```

仓库的 CI 只运行确定性测试，不会接收 Exa、LLM 或 Embedding 凭证。

## 项目边界

- Domain Atlas 是一个受控的、以证据为中心的工作流系统，并不宣称具备完全自主的通用 Agent 能力。
- 来源引用代表系统当前可获得的证据，不保证事实完备性，也不代表对目标网站内容拥有法律权利。
- 搜索排名和网站可访问性属于外部依赖。引导模式可能暂停并请求用户手动确认，而不会基于不足的证据伪造一个看似可信的知识库。
- 公开 Demo 是固定案例的完整性检查，不是通用基准测试，也不代表生产环境中的准确率承诺。

## 开发与发布

- [三个核心流程源码入门指南](docs/core-workflows-guide.md)
- [贡献指南](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)
- [v0.1.0 发布说明与远程发布检查清单](docs/release-notes/v0.1.0.md)
- [私有单用户部署与备份恢复](docs/private-deployment.md)
- [规格驱动的迭代记录](specs/iterations/)

## 开源许可

[MIT](LICENSE)
