# Domain Atlas 私有单用户部署

本文用于部署仅由一个 GitHub 账号访问的可写 Domain Atlas。公开作品集继续使用根目录的 `render.yaml`；私有实例使用 `render.private.yaml`，两者不共享服务、磁盘、数据库或 Provider 凭证。

## 运行边界

| 模式 | 用途 | 登录 | 数据写入 |
| --- | --- | --- | --- |
| `local` | 本机开发与完整使用 | 不需要 | 允许 |
| `public_demo` | 简历公开演示 | 不需要 | 禁止 |
| `private_owner` | 个人远程学习空间 | 唯一 GitHub owner | 允许 |

私有模式没有注册、密码、角色或团队功能。GitHub 只负责证明账号身份，Domain Atlas 只接受 `OWNER_GITHUB_USER_ID` 配置的 numeric user ID。

## 为什么不能使用 Render Free

Render Free Web Service 的文件系统是临时的，服务休眠、重启或重新部署后，本地 SQLite、Chroma 和上传资料都会丢失。Render 持久化磁盘只支持付费 Web Service、Private Service 或 Worker。

- [Render Free 限制](https://render.com/docs/free)
- [Render Persistent Disks](https://render.com/docs/disks)
- [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec)

`render.private.yaml` 因此使用 `starter` Web Service、单实例和挂载到 `/app/data` 的磁盘。磁盘限制服务只能运行一个实例，但这与本项目的单用户、单进程 SQLite 架构一致。

## 1. 创建 GitHub OAuth App

在 GitHub **Settings → Developer settings → OAuth Apps → New OAuth App** 创建一个专用于私有 Domain Atlas 的 OAuth App。

配置示例：

```text
Application name: Domain Atlas Private
Homepage URL: https://<private-service>.onrender.com
Authorization callback URL: https://<private-service>.onrender.com/auth/callback
```

记录 Client ID，并生成 Client Secret。Callback URL 必须与部署环境变量完全一致。生产 URL 必须使用 HTTPS。

获取自己的稳定 numeric user ID：

```bash
curl --fail --silent https://api.github.com/users/<github-login> | python -c \
  'import json,sys; print(json.load(sys.stdin)["id"])'
```

不要使用可修改的 login 或邮箱作为 owner 判断依据。

## 2. 创建 Render 私有服务

在 Render Dashboard 中创建新的 Blueprint，并选择仓库中的 `render.private.yaml`。不要把现有公共 Demo Blueprint 改成私有实例。

Blueprint 会声明：

- Docker Web Service；
- `starter` 付费实例；
- Singapore region；
- `/health` 健康检查；
- `/app/data` 持久化磁盘；
- `DEPLOYMENT_MODE=private_owner`；
- 每日应用备份和 7 份保留策略。

首次创建时，Render 会要求填写所有 `sync: false` 变量：

```text
GITHUB_OAUTH_CLIENT_ID
GITHUB_OAUTH_CLIENT_SECRET
GITHUB_OAUTH_CALLBACK_URL
OWNER_GITHUB_USER_ID
EXA_API_KEY
LLM_BASE_URL
LLM_API_KEY
CHAT_MODEL
EMBEDDING_BASE_URL
EMBEDDING_API_KEY
EMBEDDING_MODEL
EMBEDDING_DIMENSIONS
```

`SESSION_SECRET` 由 Render 生成。轮换它会立即使全部现有登录会话失效。Provider 值应与本地 `.env` 中已经通过 smoke test 的配置一致。

## 3. 首次验证

服务启动日志不应出现缺失认证配置、相对 `DATA_DIR` 或不可写目录错误。依次验证：

1. `/health` 返回 `200`；
2. 访问根路径跳转到 GitHub 登录页；
3. 非 owner GitHub 账号得到拒绝；
4. owner 登录后可以创建项目；
5. 上传一份小型 Markdown，完成摄取并打开 Wiki；
6. 手动重新部署服务，确认项目与 Wiki 仍然存在；
7. 手机浏览器可以打开项目、Wiki、学习路线和问答。

不要在 Render 日志中打印 `.env`、OAuth code、Cookie 或 Provider 响应正文。

## 备份与恢复

手动创建带 manifest 和 SHA-256 的备份：

```bash
uv run domain-atlas backup
```

指定独立输出目录：

```bash
uv run domain-atlas backup --output-dir /secure/domain-atlas-backups
```

恢复只允许写入不存在或为空的目录：

```bash
uv run domain-atlas restore /secure/domain-atlas-backups/domain-atlas-*.tar.gz \
  --target-dir /absolute/empty/data-dir
```

恢复过程会先验证 archive 路径、manifest、文件大小和 checksum，然后重写 Source 文件路径并运行 SQLite `quick_check`。不要在正在使用的 `DATA_DIR` 上原地恢复。

`BACKUP_ENABLED=true` 时，应用按 `BACKUP_INTERVAL_HOURS` 定时创建相同格式的备份，并只保留 `BACKUP_RETENTION_COUNT` 份。默认 Blueprint 把备份放在同一持久化磁盘；Render 还会为磁盘创建每日快照，至少保留 7 天。应用备份适合导出与逻辑迁移，Render Snapshot 用于私有实例的整盘恢复。

## 会话撤销

轮换 `SESSION_SECRET` 可以让全部 Session Hash 失效。也可以在相同环境中执行：

```bash
uv run domain-atlas revoke-sessions
```

## 本地验证私有模式

本地 GitHub OAuth App 可以使用：

```text
Homepage URL: http://localhost:8000
Authorization callback URL: http://localhost:8000/auth/callback
```

然后配置绝对数据路径：

```dotenv
DEPLOYMENT_MODE=private_owner
DATA_DIR=/absolute/path/to/domain-atlas-data
PERSISTENT_DATA_ACKNOWLEDGED=true
GITHUB_OAUTH_CALLBACK_URL=http://localhost:8000/auth/callback
SESSION_COOKIE_SECURE=true
```

应用只对 localhost callback 允许 HTTP；其他主机必须使用 HTTPS。确定性测试使用 Fake OAuth Provider，不会联系 GitHub，也不需要真实 Secret。
