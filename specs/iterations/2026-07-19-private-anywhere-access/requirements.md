# Private Anywhere Access Requirements

## Purpose

将 Domain Atlas 从“本地完整版本 + 公共只读作品集”扩展为可随时访问的私有、可写、单用户学习助手。新增能力必须保持个人工具边界，不演变为多用户 SaaS，也不能削弱现有公共 Demo 的隔离性。

## Runtime Modes

应用必须支持三个显式运行模式：

- `local`：本地完整可写，不要求登录；
- `public_demo`：匿名只读，只使用版本化 Demo 数据；
- `private_owner`：远程完整可写，只有配置的唯一 GitHub 用户可以访问。

现有 `PUBLIC_DEMO_MODE` 必须保持向后兼容，但新部署和文档使用显式模式配置。冲突配置必须在启动时失败，不允许静默选择较弱的安全模式。

## Owner Authentication

- 私有模式使用 GitHub OAuth Web Application Flow，授权请求必须包含不可预测 `state` 和 PKCE `S256` challenge。
- OAuth 回调必须原子消费一次性 state，校验有效期，并使用 verifier 换取临时 access token。
- 每次登录必须调用 GitHub `/user` 重新获取身份；只比较稳定的 numeric user ID。
- OAuth access token 只在回调期间存在，不写入数据库、Cookie 或日志。
- 只有 `OWNER_GITHUB_USER_ID` 对应用户可以创建会话，其他账号得到明确拒绝且不创建 Session。
- Session Token 必须使用密码学安全随机数，数据库只存储带 `SESSION_SECRET` 的摘要。
- Session Cookie 必须为 `HttpOnly`、`SameSite=Lax`、路径 `/`，私有部署中必须为 `Secure`。
- Session 支持过期、主动退出、全部撤销；轮换 `SESSION_SECRET` 后旧 Session 必须自动失效。
- 私有模式除健康检查、静态资源和认证入口外，所有业务页面与 API 都必须要求 owner Session。
- 所有修改状态的业务请求必须校验 Session 绑定的 CSRF Token。
- 认证和 CSRF 使用 FastAPI 请求依赖集中执行；后台 Runner 和 Provider 继续由应用工厂管理。

## Persistence And Backup

- SQLite、Chroma、上传文件、摄取后的原始与规范化资料全部位于 `DATA_DIR` 下。
- 私有模式启动时必须检查 `DATA_DIR` 为绝对路径、可创建、可读写，且不能是系统临时目录。
- 私有部署必须显式声明数据位于持久化磁盘；不允许使用 Render Free 的临时文件系统作为私人数据存储。
- 提供一致性备份命令。备份必须包含 SQLite 在线快照、Chroma、上传及资料文件、版本化 manifest 和 SHA-256 校验。
- 备份输出不得递归包含备份目录本身、`.env`、OAuth Secret、Provider Key 或 Session 明文。
- 提供只恢复到空目录的恢复命令，恢复前校验 manifest、所有 checksum 和 archive member 路径。
- 提供应用内定时备份的最小实现，支持启用开关、间隔和保留数量；默认关闭。
- 恢复测试必须证明项目、Wiki 和资料文件可从干净目录重新读取。

## Interrupted Workflow Recovery

- 应用启动时继续把遗留的 `queued`/`running` 任务标记为 `interrupted`。
- UI 必须用中文说明任务因进程重启中断，并提供适用于该任务类型的重试操作。
- 重试必须重新建立独立 Run，保留旧 Run 的错误与步骤历史，并记录 `retry_of_run_id`。
- 只允许重试 `interrupted` 或 `failed` 的受支持任务，且同一项目存在活动任务时拒绝重试。
- `ingest_source` 重试必须复用原 Source；`knowledge_build` 必须沿用现有原子替换行为；`guided_autopilot` 必须沿用 URL 唯一约束和候选替换策略，避免不可控重复数据。
- 本轮不要求从原步骤自动续跑，也不引入外部队列。

## Deployment And Operations

- 公共 Render Blueprint 必须保持 Free、无磁盘、无 Provider Secret、只读。
- 增加独立的私有 Render Blueprint 示例：付费单实例 Web Service、挂载 `/app/data` 的持久化磁盘、`/health` 健康检查和 secret 环境变量声明。
- 部署文档必须引用并说明 Render 的临时文件系统、付费磁盘、每日磁盘快照和单实例限制。
- GitHub OAuth callback、数据目录、Cookie 安全策略和所有必要环境变量必须在中文文档中列出。
- 真实 Secret、私人数据、备份包和运行时 Session 不得进入 Git。
- 未获得本轮明确授权，不 push、不创建或修改线上服务。

## Mobile Usability

- 确定性 Playwright 回归必须覆盖桌面和手机视口。
- 覆盖登录入口、项目列表/创建、项目页、构建状态、Wiki、学习路线和问答。
- 页面不得发生横向溢出、主要控件不可点击、长任务状态遮挡或无法返回项目导航。

## Out Of Scope

- 注册、密码登录、找回密码、多用户表、RBAC、项目成员和租户隔离；
- PostgreSQL、ORM 或 request-scoped database Session 重写；
- Celery、Redis、Kafka、分布式 Worker 或自动任务续跑；
- 全面 asyncio 改造；
- 对现有搜索、知识构建、检索和 Prompt 的无关修改。

## Acceptance Criteria

1. 三种模式均有配置和路由边界测试，旧公共模式配置继续工作。
2. Fake GitHub OAuth 完整证明 state、PKCE、owner allowlist、Session Hash、Cookie、退出和 CSRF 行为。
3. public Demo 保持匿名只读，private owner 未认证时无法读取或修改私人内容。
4. 数据目录启动检查能阻止私有模式使用相对路径或临时路径。
5. 备份恢复 round trip 在干净目录恢复项目、Wiki、SQLite、Chroma/资料文件，并拒绝损坏或危险 archive。
6. 中断任务在 UI 中可见且可以安全创建关联的新 Run。
7. 私有部署配置明确使用持久化磁盘，公共部署配置保持不变且不含秘密。
8. 桌面和手机 Playwright 核心流程通过。
9. fast、deterministic E2E、golden Demo、browser E2E 以及一次真实 live E2E 全部通过。
