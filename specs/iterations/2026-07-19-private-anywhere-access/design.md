# Private Anywhere Access Design

## Current-State Findings

- 当前 FastAPI 应用只有布尔 `PUBLIC_DEMO_MODE`：关闭时为本地可写，开启时由中间件限制到固定 Demo。
- 应用级 Provider、Index 和 Runner 已由 `create_app(...)` 组装并支持测试替身，Repository 使用短生命周期 SQLite 连接；无需引入 ORM。
- 所有持久数据已以 `DATA_DIR` 为根，但缺少私有部署路径校验、备份和恢复契约。
- 后台线程的 Run 状态已持久化，启动时也会标记遗留任务为 `interrupted`，但 UI 没有任务类型感知的重试入口，也没有新旧 Run 关联。
- Render 官方文档确认 Free Web Service 使用临时文件系统，休眠、重启或部署都会丢失 SQLite 和上传文件；持久化磁盘只适用于付费服务，并且磁盘一次只能挂载到一个实例。

## Mode Resolution

新增 `deployment_mode: Literal["local", "public_demo", "private_owner"]`。为兼容现有公开部署：

1. 显式设置 `DEPLOYMENT_MODE` 时以它为准；
2. 未显式设置且 `PUBLIC_DEMO_MODE=true` 时解析为 `public_demo`；
3. 其他情况为 `local`；
4. `DEPLOYMENT_MODE` 与 `PUBLIC_DEMO_MODE` 冲突时启动失败。

公开模式继续在数据库和 Provider 构造前形成硬边界。私有模式在数据库初始化前验证配置与持久化目录。

## Authentication Components

### OAuth Provider Boundary

定义小型 `GitHubOAuthProvider` 协议：生成授权 URL、用 code/verifier 换 token、用 token 获取 `{id, login, avatar_url}`。生产实现使用同步 `httpx.Client`，Fake 实现通过 `create_app` 注入。

授权请求不申请仓库或邮箱 scope，只读取公开身份。state 记录包含：state hash、PKCE verifier 的加密无关明文、原始安全 return path、过期时间和消费时间。verifier 是一次性短期秘密，存放在服务端 SQLite，而不是 Cookie。

### Session Repository

新增两张无用户体系的本地表：

- `oauth_states`：短期一次性 OAuth transaction；
- `owner_sessions`：token digest、GitHub numeric ID/login、过期与撤销时间。

Session 摘要使用 `HMAC-SHA256(SESSION_SECRET, token)`；CSRF Token 使用不同 purpose 从当前 Session Token 派生，不额外落库。Secret 轮换会同时使旧 Session 和 CSRF 失效。Cookie 只保存原始高熵 Session Token；数据库泄露时无法直接重放。

### FastAPI Dependencies

- `get_owner_session`：读取 Cookie、校验摘要/过期/owner ID，并把有效 Session 返回给请求；
- `require_owner`：私有模式缺失 Session 时对页面重定向登录，对非页面请求返回 401；
- `verify_csrf`：在 owner Session 基础上校验表单或 `X-CSRF-Token`；
- `require_project` 只在能明显消除重复查找时引入，不扩大本轮重构范围。

认证入口、健康检查和静态资源留在公开 Router；现有正常业务路由集中挂到受保护 Router。local 模式的依赖返回本地 owner context 且不要求 Cookie，保持开发体验；public Demo 的硬 allowlist 继续先于业务路由。

模板中的所有 POST form 注入 CSRF hidden input。登出使用 POST，不使用会被跨站触发的 GET。

## Persistence And Backup

### Startup Validation

`private_owner` 要求绝对 `DATA_DIR` 和显式 `PERSISTENT_DATA_ACKNOWLEDGED=true`，拒绝把系统临时根目录本身作为数据目录。应用创建目录并执行原子 probe write/rename/delete。配置缺失、目录不可写、OAuth/Session Secret 缺失都使用安全、可操作的启动错误。

### Backup Format

备份由标准库实现，格式为 `.tar.gz`：

1. 通过 SQLite backup API 生成一致的数据库快照；
2. 在单进程维护锁下复制 Chroma、uploads 与其他 `DATA_DIR` 文件；
3. 生成 `manifest.json`，记录 schema version、创建时间、应用版本、相对路径、大小和 SHA-256；
4. 将数据库内的 Source 文件路径转换为 `@data/` 可移植标记；恢复时重写到新数据根目录；
5. archive 只包含 `manifest.json` 和 `payload/` 下的文件。

恢复先在临时目录中完成安全解包和 checksum 校验，再原子移动到必须为空的目标目录。拒绝绝对路径、`..`、symlink、重复 member、未知顶层路径和校验不符。

Web 写请求与后台任务持有数据目录共享锁，备份获取独占锁，使 SQLite 快照和文件复制不会与摄取、上传或构建并发。应用内 `BackupScheduler` 只在显式启用时启动 daemon thread，按间隔调用相同备份服务，并按创建时间保留最近 N 个。调度器不负责外部对象存储；Render 磁盘自己的每日快照提供独立的基础设施恢复层。

完成性审计进一步约束上传路径：客户端文件名只作为归一后的显示元数据，不参与磁盘路径拼接；实际文件使用 Source ID 目录和服务端固定文件名，因此绝对路径、`..` 和 Windows 反斜杠都不能逃逸 `DATA_DIR`。所有 `/domains` 写路由统一挂载到同时包含 owner、CSRF 和数据锁依赖的 Router，新增写路由时由结构测试约束该边界。

## Workflow Retry

`workflow_runs` 增加可空 `retry_of_run_id` 外键。Repository 提供按 ID 获取和校验 retry eligibility 的原子方法。Web 重试端点只接受原 Run ID，并从服务端 Run/Step 输出恢复必要参数，禁止客户端提交任意 workflow name 或 source ID。

支持映射：

- `source_ingestion`：从已持久化 step output 或 workflow run payload 读取 source ID；
- `knowledge_build`：按 project ID 重新构建；
- `guided_autopilot`：按 project ID 重新执行。

为保证参数可靠，所有新 Run 增加 `input_json`，原始提交时即记录最小可重放输入。旧 Run 缺少输入时，UI 说明不能安全自动重试，允许用户回到对应原始操作。

## Deployment Shape

- `render.yaml` 保持公共 Free Demo，不做任何磁盘或 Secret 修改。
- `render.private.yaml` 作为独立 Blueprint 示例，声明付费单实例、`/app/data` 磁盘和 `DEPLOYMENT_MODE=private_owner`。
- OAuth、Provider 和 Session 值使用 `sync: false` secret 占位，绝不提供默认值。
- 容器继续使用非 root 用户；启动验证确保磁盘挂载权限正确。

真实私有部署必须等待：用户创建 GitHub OAuth App、提供 callback URL 对应配置，并明确接受 Render 付费 Web Service 和磁盘。代码阶段使用 Fake Provider 完成确定性验证。

## Verification Strategy

1. 配置、Repository 和安全原语单元测试。
2. TestClient + Fake OAuth 完成完整登录、拒绝、CSRF、退出和三模式路由回归。
3. 备份/恢复 round trip 与恶意 archive 测试。
4. 工作流中断与 retry linkage 测试。
5. Fake OAuth 浏览器服务覆盖桌面和手机流程。
6. 运行现有所有确定性回归；真实 Provider 只在最终 gate 运行一次。
