# Public Demo Render Deployment Design

## Current-State Findings

- `PUBLIC_DEMO_MODE=true` 已跳过数据库初始化，并通过首层中间件只允许公共 GET/HEAD 路由。
- Demo 数据来自版本控制内的内存 Catalog，不依赖数据库、文件或 Provider。
- 现有 Dockerfile 已采用多阶段构建和非 root 用户，但启动命令固定监听 `8000`。
- 现有 CI 已覆盖 fast、E2E、黄金 Demo 和 Playwright 回归，且不注入 Provider 凭证。
- 本机未安装 Render CLI，因此本轮使用 YAML 解析和字段级测试作为确定性校验；真实平台校验留在经授权的首次部署阶段。

## Delivery Design

### Container Port Contract

Docker 镜像声明默认 `PORT=8000`，启动命令在运行时展开该变量，并保持 `0.0.0.0`。这使本地命令无需额外配置，同时兼容 Render 注入的端口。

### Render Blueprint

根目录 `render.yaml` 只声明一个 Docker Web Service：

- `runtime: docker`
- `plan: free`
- `region: singapore`
- `healthCheckPath: /health`
- `autoDeployTrigger: checksPass`
- 唯一应用环境变量为 `PUBLIC_DEMO_MODE=true`

不声明磁盘、数据库或秘密变量。Free 计划可在首次部署后按需升级，而无需改变代码中的安全边界。

### Deployment Configuration Test

开发依赖增加 YAML 解析器。确定性测试读取 `render.yaml` 和 Dockerfile，验证：

- Blueprint 只有一个公共 Docker 服务；
- 区域、计划、健康检查、自动部署和公共模式值正确；
- 不存在磁盘、数据库或敏感环境变量；
- Dockerfile 以非 root 用户运行，并遵守 `PORT` 默认值和 `0.0.0.0` 绑定。

该测试不是 Render 服务端 Schema 验证的替代品。首次授权部署时仍需由 Render 解析 Blueprint，并以平台构建和健康检查作为最终证据。

## Remote Probe Design

`scripts/smoke_public_demo_remote.py` 使用 `httpx`，流程如下：

1. 校验 base URL 仅使用 HTTP/HTTPS 且不携带凭证、查询或 fragment。
2. 在有限总期限内轮询 `/health`，允许冷启动期间的连接失败和临时 5xx。
3. 检查根跳转和核心 Demo 页面内容。
4. 检查代表性 Wiki 内链与 HTTPS citation href，但不访问 citation 外站。
5. 确认敏感 GET 路由返回 `404`。
6. 使用空载荷确认代表性 POST 路由返回 `404`。

任何非预期状态都立即返回非零退出码。探针不读取本地 `.env`，也不接受 Provider 配置。

## Documentation And Operations

- README 在 URL 尚未产生时明确说明部署状态。
- 首次发布通过 Render Dashboard 从 Blueprint 创建服务。
- 后续提交仅在 GitHub CI 通过后自动部署。
- 回滚使用 Render 的历史部署回滚能力；回滚后重新执行远程探针。
- Free 服务空闲后可能冷启动，探针的等待窗口只用于启动恢复，不掩盖持续失败。

## Verification Strategy

1. 定向运行公共模式、安全边界和部署配置测试。
2. 构建 Docker 镜像，以非默认端口运行并执行远程探针。
3. 检查容器运行用户以及宿主机未产生运行时数据。
4. 运行全部确定性回归层。
5. 更新任务清单和迭代总结后提交，不 push。

