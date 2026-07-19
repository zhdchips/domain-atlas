# Private Anywhere Access Iteration Summary

## Outcome

Domain Atlas 已实现 `local`、`public_demo` 和 `private_owner` 三种显式运行模式。私有模式具备 GitHub OAuth 单一 Owner 认证、服务端 Session、CSRF、防临时盘误用、备份恢复和中断任务重试，并已部署到 Render Starter + 1 GB 持久化磁盘。桌面、手机、服务重启和真实备份恢复均完成验证。

## Delivered

- GitHub OAuth Authorization Code + PKCE：一次性 state、Owner 数字 ID allowlist、临时 access token 和安全回调约束。
- 服务端 Session：数据库只保存 HMAC digest；Cookie 使用 `HttpOnly`、`SameSite=Lax`，私有 HTTPS 部署强制 `Secure`。
- FastAPI `Depends`：集中保护私有读路由，并对写路由实施认证与 CSRF 校验；公共 Demo 保持匿名只读。
- 持久化启动保护：私有模式要求绝对 `DATA_DIR`、可写探针和显式持久化确认。
- 一致性备份恢复：SQLite online backup、文件锁、manifest、checksum、安全解包、空目录恢复和保留策略。
- 运维 CLI：`domain-atlas backup`、`restore` 和 `revoke-sessions`。
- 中断任务恢复：持久化最小重放输入、retry lineage、活动任务冲突保护和中文 UI。
- 私有 Render Blueprint：Starter 单实例、1 GB 持久化磁盘、Secret 仅声明为平台输入项。
- 私有部署中文文档、三模式 `.env.example` 和 README 入口。
- Fake OAuth Playwright：桌面与 390 x 844 手机视口覆盖登录、项目创建、Uvicorn 重启后项目与 Session 持久化、长任务、Wiki、学习路线、问答和登出。
- 完成性审计加固：上传的客户端文件名不再参与磁盘路径拼接，所有领域写路由统一使用 owner、CSRF 和数据锁 Router。
- 首次真实私有部署发现 FastAPI 0.139 已移除应用级 `add_event_handler`；备份调度器改由 lifespan 启停，并增加生产 Blueprint 配置回归。
- 真实手机视口发现 Render 内部 HTTP scheme 生成 mixed-content 静态资源 URL；CSS/JavaScript 改为同源相对路径并增加反向代理回归。

## Verification Evidence

- 生产生命周期修复后快速回归：`172 passed`；离线 Intake 评测 `13/13 PASS`。
- 反向代理静态资源修复后快速回归：`173 passed`；离线 Intake 评测 `13/13 PASS`。
- Render 官方 `render.yaml` JSON Schema：`render.yaml` 与 `render.private.yaml` 均通过。
- 阶段部署、配置与备份测试：`17 passed`。
- `uv run python scripts/regression.py --fast`：完成性加固后 `171 passed`；离线 Intake 评测 13/13 通过。
- `uv run python scripts/regression.py --e2e`：`3 passed`。
- `uv run python scripts/regression.py --golden-demo-eval`：`25 / 25`。
- `uv run python scripts/regression.py --browser-e2e`：Wiki/学习路线、公共 Demo、私有 Owner 桌面与手机三套浏览器回归全部通过。
- `uv run python scripts/regression.py --live-e2e`：通过，耗时 161.7 秒；生成 19 个 Wiki 页面、5 个学习模块、15 个课程内容块，引用问答返回 3 个 Wiki 证据。
- 公共线上 Demo 远程冒烟：`https://domain-atlas-demo.onrender.com` 通过，公开只读边界保持有效。
- Docker BuildKit：私有检查镜像构建通过。
- 私有容器运行：非 root `domainatlas` 用户在独立持久化卷创建 SQLite，`/health` 通过。
- 真实私有服务：`https://domain-atlas-private.onrender.com`，Starter + 1 GB 磁盘，Render 页面合计 `$7.25 / month`，健康检查 200。
- 真实 GitHub OAuth：未授权访问进入登录页，数字 Owner allowlist 登录成功，OAuth state + PKCE 回调成功。
- 真实 Owner 写链路：创建 `FastAPI 生产部署` 项目，摄取 2 个独立来源族和 8 个 chunks；首次无效 JSON 可恢复失败后重试成功，生成 16 个 Wiki 页面、5 阶段课程和带 Wiki/source provenance 的引用问答。
- 真实重启持久化：Render `Restart service` 经历 502 到 200；重启后 Owner Session、项目、Wiki 和问答记录仍可访问。
- 真实手机访问：390 x 844 视口下导航、课程正文和引用正常；静态资源使用同源相对 URL，无 mixed-content。
- 真实备份恢复：持久磁盘生成校验归档，隔离目录恢复后 `quick_check=ok`、`projects=1`、`wiki=16`。
- Git 审计：未跟踪 `.env`、数据库、Session、私人数据或备份包；未发现 API Key、GitHub Token 或私钥模式。

## Phase Commits

- `b2bd4cf` `docs: specify private anywhere access iteration`
- `dc8528c` `feat: protect private owner mode with GitHub OAuth`
- `d239089` `feat: add durable backup and restore tooling`
- `791874b` `feat: add recoverable workflow retries`
- `bfdf352` `feat: add private deployment and mobile regression`
- `df3ca4f` `docs: record private access verification`
- `747c076` `fix: keep private uploads inside persistent storage`
- `d4610e1` `test: verify private data survives restart`
- `91f0626` `fix: start backup scheduler with FastAPI lifespan`
- `5c109d8` `fix: use same-origin static asset URLs`

## External Deployment Gate

外部部署门已由用户明确授权并完成。GitHub OAuth App、Render 付费服务、持久化磁盘和 Secret 均只配置在外部平台；仓库没有写入凭据。

## Operational Boundary

- 私有模式是单 Owner、单实例设计，不提供注册、多用户、RBAC 或租户隔离。
- SQLite、Chroma、资料文件和 Session 共享同一个持久化目录；不能横向扩容多个 Web 实例。
- 应用备份提供可迁移归档；Render 磁盘快照属于平台级补充，不能替代应用恢复演练。
- 失败或中断任务通过显式新 Run 重试，不自动恢复任意进程内执行状态。
