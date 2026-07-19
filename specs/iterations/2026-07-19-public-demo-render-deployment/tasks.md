# Public Demo Render Deployment Tasks

## Specification

- [x] 审计 Dockerfile、公共模式白名单、Provider 构造、CI 和现有 Demo 测试。
- [x] 定义 Render、动态端口、远程探针和外部发布权限边界。
- [x] 编写 requirements.md、design.md 和 tasks.md。

## Implementation

- [ ] 让 Docker 容器遵守运行时 `PORT` 并保留本地默认值 `8000`。
- [ ] 增加最小且无秘密信息的 `render.yaml`。
- [ ] 增加 Render YAML/字段和 Docker 交付契约的确定性测试。
- [ ] 增加可传入 base URL 的远程只读冒烟测试。
- [ ] 更新中文 README 的部署、验证、冷启动和回滚说明。

## Verification

- [ ] 运行部署配置和公共 Demo 定向测试。
- [ ] 构建 Docker 镜像并以自定义端口运行。
- [ ] 对本地容器执行远程只读冒烟测试。
- [ ] 验证容器为非 root 且未创建宿主运行时数据。
- [ ] 运行 `uv run python scripts/regression.py --fast`。
- [ ] 运行 `uv run python scripts/regression.py --e2e`。
- [ ] 运行 `uv run python scripts/regression.py --golden-demo-eval`。
- [ ] 运行 `uv run python scripts/regression.py --browser-e2e`。

## Delivery

- [ ] 编写 iteration-summary.md，记录测试证据、Render CLI 验证限制和剩余发布步骤。
- [ ] 提交当前分支，不 push。
- [ ] 获得用户明确确认后，push 并创建 Render 公共服务。
- [ ] 对真实 HTTPS URL 执行远程只读冒烟测试并更新 README。
