# Public Demo Render Deployment Requirements

## Purpose

将现有 `PUBLIC_DEMO_MODE` 收口为可重复、可审计的 Render Docker 部署，使陌生人可以通过 HTTPS 浏览固定 Demo，同时不接触正常项目、运行时数据、写操作或外部 Provider。

## Scope

- 使用当前 FastAPI、Jinja 和 Docker 交付形态，不迁移为静态站点或其他运行时。
- 增加 Render Blueprint、云平台动态端口适配、远程只读冒烟测试和中文部署文档。
- 保留正常本地模式的现有行为。
- 创建 Render 服务、push 代码、配置域名及任何可能产生费用的操作，必须等待用户明确确认。

## Functional Requirements

### Container And Render

- 容器必须监听 `0.0.0.0`。
- 容器必须使用运行时 `PORT`，未设置时默认使用 `8000`。
- 根目录 `render.yaml` 必须声明 Docker Web Service、Singapore 区域、`/health` 健康检查和 `PUBLIC_DEMO_MODE=true`。
- Render 自动部署必须等待 GitHub CI 检查通过。
- Blueprint 不得声明数据库、磁盘、Provider Key 或其他秘密配置。

### Public Read-Only Boundary

- 公共模式只允许 `/`、`/health`、`/demo`、`/demo/**` 和 `/static/**` 的 GET/HEAD 请求。
- `/domains`、`/docs`、`/openapi.json` 及其他正常应用路由必须返回 `404`。
- 创建项目、上传、搜索、摄取、构建、自动构建和问答等写请求必须返回 `404`。
- 公共模式不得初始化或读取 SQLite、Chroma、上传目录或本地项目数据。
- 公共模式不得构造或调用 Exa、LLM、Embedding、URL 摄取等 Provider。
- Docker 构建上下文不得包含 `.env`、`data`、`uploads`、`reports`、测试数据或本地数据库。

### Remote Smoke Check

- 提供一个接收 `--base-url` 的命令行探针，可用于本地容器和真实 HTTPS 地址。
- 首次健康检查允许有限重试，以覆盖 Render Free 冷启动；超过总期限后必须失败。
- 探针必须检查健康状态、根跳转、核心 Demo 页面、代表性 Wiki 内链、学习路线、预生成引用问答和黄金评测。
- 探针只验证外部 citation 的安全链接，不抓取第三方网站。
- 探针必须先确认 Demo 边界，再验证受保护 GET 和 POST 路由均为 `404`。
- 探针不得发送能创建项目或触发 Provider 的有效业务载荷。

### Documentation

- README 必须说明 Render Blueprint 部署、远程验证、自动部署、回滚和 Free 冷启动限制。
- 未获得正式公网 URL 前必须明确标注“尚未部署”，不得伪造在线地址。
- README 不得要求或暗示给只读 Demo 配置 Provider 凭证。

## Acceptance Criteria

1. Docker 镜像构建成功，使用自定义 `PORT` 运行时 `/health` 返回 `200`。
2. 本地容器中 `/` 跳转 `/demo`，全部核心 Demo 页面可访问，受保护路由全部返回 `404`。
3. 公共模式运行期间不创建数据目录或数据库，不调用外部 Provider。
4. `render.yaml` 通过 YAML 解析和字段级自动校验；若未使用 Render CLI，迭代总结明确记录该限制。
5. 远程只读冒烟测试可针对本地容器运行通过。
6. `--fast`、`--e2e`、`--golden-demo-eval` 和 `--browser-e2e` 全部通过，且不消耗 Provider 额度。
7. `PUBLIC_DEMO_MODE=false` 时正常项目创建及现有业务回归保持通过。
8. 代码与配置通过 Git 提交保存，但在用户确认前不 push、不创建 Render 服务。

