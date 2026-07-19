# Private Anywhere Access Tasks

## Phase 1: Specification

- [x] 审计运行模式、应用工厂、SQLite、后台任务、Docker、Render 和分层回归。
- [x] 核对 Render 持久化磁盘与 Free Web Service 的当前官方限制。
- [x] 定义 GitHub OAuth、Session、CSRF、持久化、备份和任务重试边界。
- [x] 编写 requirements.md、design.md 和 tasks.md。
- [x] 运行文档与工作树检查并提交阶段结果。

## Phase 2: Private Owner Authentication

- [x] 增加三种显式运行模式及旧环境变量兼容校验。
- [x] 增加 GitHub OAuth Provider 协议、生产适配器和可注入 Fake。
- [x] 增加 OAuth state、owner Session 和 HMAC digest 持久化。
- [x] 使用 FastAPI Depends 集中实现 owner 认证与 CSRF。
- [x] 增加登录、回调、拒绝、登出页面和导航状态。
- [x] 为所有现有写表单注入 CSRF Token。
- [x] 增加认证、Cookie、模式边界和公开 Demo 回归测试。
- [x] 运行阶段测试并提交。

## Phase 3: Persistence And Backup

- [ ] 增加 private owner 数据目录启动校验。
- [ ] 实现一致性备份、manifest 和 checksum。
- [ ] 实现安全恢复到空目录。
- [ ] 增加可配置备份调度与保留策略。
- [ ] 增加 CLI 命令和备份恢复 round-trip/安全测试。
- [ ] 运行阶段测试并提交。

## Phase 4: Interrupted Workflow Retry

- [ ] 为 Run 持久化最小可重放输入和 retry 关联。
- [ ] 增加 Repository 的原子 retry eligibility 检查。
- [ ] 为摄取、知识构建和 Guided Autopilot 增加安全重试端点。
- [ ] 更新中断状态中文提示和可用/不可用重试 UI。
- [ ] 增加中断、冲突、关联和幂等回归测试。
- [ ] 运行阶段测试并提交。

## Phase 5: Private Deployment And Mobile UX

- [ ] 增加不含 Secret 的私有 Render Blueprint 示例。
- [ ] 更新 `.env.example`、README 和私有部署操作文档。
- [ ] 增加部署配置与持久化契约测试。
- [ ] 增加 Fake OAuth 桌面/手机 Playwright 回归。
- [ ] 修复发现的移动端溢出、交互和导航问题。
- [ ] 运行阶段测试并提交。

## Phase 6: Final Verification

- [ ] 运行 fast 回归。
- [ ] 运行 deterministic E2E。
- [ ] 运行 golden Demo evaluation。
- [ ] 运行全部 browser E2E。
- [ ] 运行一次现有真实 live E2E。
- [ ] 检查 Git 中无 Secret、私人数据、Session 和备份包。
- [ ] 编写 iteration-summary.md，记录证据和真实部署待办。
- [ ] 提交最终阶段，不 push、不修改线上服务。

## External Deployment Gate

- [ ] 用户创建并配置 GitHub OAuth App。
- [ ] 用户确认付费 Render Web Service 与持久化磁盘。
- [ ] 获得明确授权后 push 并创建 private owner 服务。
- [ ] 验证真实 OAuth、重启后持久化、移动端访问和备份恢复。
