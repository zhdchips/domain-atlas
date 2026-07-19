# Public Demo Render Deployment Iteration Summary

## Outcome

Domain Atlas 的公开只读 Demo 已部署到 Render Free Web Service，并通过公网 HTTPS 地址 [https://domain-atlas-demo.onrender.com](https://domain-atlas-demo.onrender.com) 对外提供访问。

## Delivered

- Docker 容器现在遵守运行时 `PORT`，默认仍为 `8000`，并继续绑定 `0.0.0.0`、使用非 root 用户。
- 根目录增加 `render.yaml`，声明 Singapore Free Docker Web Service、`/health`、CI 通过后自动部署，以及唯一应用环境变量 `PUBLIC_DEMO_MODE=true`。
- 增加部署契约测试，约束 Blueprint、环境变量、非 root 运行和 Docker 构建上下文。
- 增加 `scripts/smoke_public_demo_remote.py`，可验证本地容器或真实 HTTPS Demo，并覆盖核心页面、Wiki 内链、citation href 和读写路由隔离。
- 中文 README 增加当前在线状态、Render Blueprint、冷启动、远程验证和回滚说明；没有伪造尚不存在的 URL。

## Verification Evidence

- Render 官方 `render.yaml` JSON Schema：通过。
- 定向部署与公共模式测试：`16 passed`。
- Docker BuildKit 构建：通过，镜像 `domain-atlas:render-check`。
- Docker 运行：以 `PORT=18988`、`USER=domainatlas`、只读根文件系统和 `DATA_DIR=/app/absent-data` 启动成功。
- 本地容器远程探针：通过；核心 Demo 页面为 `200`，受保护 GET/POST 路由为 `404`。
- 不存在的 `/app/absent-data` 在探针完成后仍未被创建。
- 镜像中不存在 `.env`、tests、scripts、reports 或 uploads；镜像环境不包含 Provider Key。
- `uv run python scripts/regression.py --fast`：通过，`147 passed`，离线 Intake 评测 13/13 通过。
- `uv run python scripts/regression.py --e2e`：通过，`3 passed`。
- `uv run python scripts/regression.py --golden-demo-eval`：通过，`25 / 25`。
- `uv run python scripts/regression.py --browser-e2e`：通过，项目 UI 和公共只读 Demo 两套 Playwright 回归均通过。
- Render Blueprint 首次同步：通过，部署提交为 `d09e4c1`，服务计划为 Free，区域为 Singapore。
- Render 内部 `/health` 检查：通过，服务成功监听平台注入的端口 `10000`。
- 公网远程探针：通过，核心 Demo 页面为 `200`，敏感 GET/POST 路由为 `404`。
- 公网浏览器检查：通过，首页展示固定 `Agent Harness Engineering` Catalog 及只读状态说明。
- 未运行任何 live Provider 测试，Provider 费用为零。

## Validation Boundary

本机没有安装 Render CLI，因此未执行 `render blueprints validate`。本轮直接下载 Render 官方 Schema 并使用 `jsonschema` 验证 Blueprint；Render 平台也已成功完成 Blueprint 解析、远端镜像构建、运行时健康检查和公网 TLS 发布。

## Operations

- Render Free 服务空闲后会休眠，首次访问可能延迟约 50 秒或更久。
- 后续 Blueprint 变更在 GitHub CI 通过后自动部署。
- 每次部署后可运行 `scripts/smoke_public_demo_remote.py` 验证公网只读边界。
- 如用于正式简历且无法接受冷启动，可将实例升级为不休眠计划。
