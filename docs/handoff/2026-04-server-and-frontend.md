# 服务层与前端（Phase 1） — Handoff Note

**日期**：2026-04-27
**状态**：进行中
**对应 Spec**：`docs/specs/server-and-frontend.md`
**变更自**：
**PR / 分支**：<!-- 待补充 -->

---

## 背景
> 感知层（daemon 模块）和数据模型已落地，现在需要构建服务层和 Web 前端，让开发者通过浏览器实时监控 pane 状态并发送指令，完成 Phase 1 端到端闭环。

## 本次交付范围
- 新增：`server/__init__.py` — 包初始化
- 新增：`server/logging.py` — 消耗 [log] 配置的集中日志初始化（RotatingFileHandler + StreamHandler）
- 新增：`server/schemas.py` — Pydantic 请求/响应模型（含 WebSocket 消息类型）
- 新增：`server/runtime.py` — compute_runtime_info 辅助函数
- 新增：`server/ws.py` — WebSocketBroadcaster + WS /ws/sessions 端点
- 新增：`server/dependencies.py` — get_database/get_broadcaster/get_tracker Depends 函数
- 新增：`server/routers/sessions.py` — GET/PATCH sessions, GET events
- 新增：`server/routers/actions.py` — POST send-keys (dry-run) + POST focus
- 新增：`server/routers/insights.py` — Phase 3+ 占位路由
- 新增：`server/main.py` — FastAPI 应用入口 + lifespan（含 daemon task 启动）
- 新增：`daemon/main.py` — Daemon 主循环（编排 5 个模块）
- 修改：`daemon/session_tracker.py` — 新增 set_transition_callback + _on_transition 回调
- 修改：`pyproject.toml` — 新增 websockets>=12.0 依赖
- 修改：`.claude/rules/logging-boundaries.md` — Globs 更新为 server/**/*.py
- 新增：`frontend/` — Vite + React + TypeScript 项目（含 Dashboard, SessionCard, FilterBar 等组件）
- 新增：5 个 Python 测试文件，33 个新增测试用例
- 新增：`tests/integration/test_service_layer.py` — 17 个服务层集成测试（TC-TRACK/ATTN/API/WS/DB）
- 修改：`daemon/session_tracker.py` — 修复 terminal status 转换时 ended_at 未写入数据库的 bug

## 重点说明
> - Daemon 作为 asyncio Task 运行在 FastAPI 进程内（共享 Database 实例）
> - WebSocket 推送通过 SessionTracker.set_transition_callback() 实现，状态变更直接触发广播
> - 前端重连使用指数退避（1s → 30s），断连期间 UI 显示断连状态
> - send-keys 的 dry-run 模式用于安全预览，前端确认对话框确认后才实际发送
> - iTerm2 跳转通过 osascript 实现，VSCode 仅降级激活窗口
> - Insight 相关接口为占位路由（GET 返回 []，PATCH 返回 501），Phase 3 再实现
> - server/logging.py 消耗已有 [log] 配置和 server_log 路径，幂等设计
> - SessionTracker callback 是新增的向后兼容 hook，现有 20 个测试全部通过

## 开发记录
> 只追加，不改写。记录过程中的决策、变更、阻塞。
- [2026-04-27] 创建 Spec 和 Handoff Note，准备开始开发
- [2026-04-27] Step 1 完成：pyproject.toml 添加 websockets>=12.0，logging-boundaries.md Globs 更新为 server/**/*.py
- [2026-04-27] Step 2 完成：server/logging.py — setup_logging(env) 幂等，RotatingFileHandler + StreamHandler，4 个测试通过
- [2026-04-27] Step 3 完成：server/schemas.py + server/runtime.py — 所有 API 请求/响应模型 + compute_runtime_info
- [2026-04-27] Step 4 完成：server/ws.py — WebSocketBroadcaster + WS /ws/sessions 端点，6 个测试通过
- [2026-04-27] Step 5 完成：server/dependencies.py — get_database/get_broadcaster/get_tracker
- [2026-04-27] Step 6 完成：server/routers/sessions.py — GET/PATCH sessions + GET events，12 个测试通过
- [2026-04-27] Step 7 完成：server/routers/actions.py — POST send-keys + POST focus，6 个测试通过
- [2026-04-27] Step 8 完成：server/routers/insights.py — Phase 3+ 占位路由
- [2026-04-27] Step 9 完成：daemon/main.py + session_tracker.py callback hook，5 个测试通过（含 20 个现有测试无回归）
- [2026-04-27] Step 10 完成：server/main.py — lifespan 绑定所有组件，daemon task 启动，on_state_change 回调
- [2026-04-27] Step 11 完成：tests/server/conftest.py — 内存 DB + httpx.AsyncClient + create_test_app
- [2026-04-27] Step 12-14 完成：frontend/ 脚手架 + hooks + 9 个组件（Dashboard, FilterBar, SessionCard, StatusBadge, QuickReply, CustomInput, SendConfirmDialog, InlineEdit, WsStatusIndicator），tsc + vite build 通过
- [2026-04-27] Step 15 完成：server/main.py 中 mount frontend/dist 静态文件
- [2026-04-27] 全部 166 个 Python 测试通过，ruff check + mypy 均通过
- [2026-04-27] 新增 17 个服务层集成测试（test_service_layer.py），覆盖 TC-TRACK-001..005、TC-ATTN-001、TC-API-001..006、TC-WS-001..003、TC-DB-001..002，全部 210 个测试通过
- [2026-04-27] 修复 session_tracker.py bug：terminal status 转换时未设置 ended_at 字段，现已在 insert 和 update 两条路径中补全
- [2026-04-27] 修复 vite.config.ts 代理端口硬编码问题：改为从 VITE_API_PORT / VITE_API_HOST 环境变量读取，scripts/dev 启动前端时注入对应端口

## 验收清单
- [ ] Dashboard 在 2 秒内加载完成，显示所有当前 tmux pane
- [ ] 状态变更通过 WebSocket 在 1 秒内推送到 UI
- [ ] 从 UI 发送 "y" 后，tmux pane 正确收到该输入
- [ ] Focus 按钮点击后，iTerm2 切换到对应 pane 并置前
- [ ] display_name / description / tags 编辑后页面刷新仍然保留
- [ ] 系统在 10+ 并发 pane 下稳定运行
- [ ] tmux pane 被关闭时，系统在 2 个 poll 周期内将其标记为 terminated
- [ ] Daemon 崩溃重启后，Server 继续提供历史数据，不丢失已收集的状态
- [ ] 无 JS 控制台错误（开发模式下 0 个 error 级别日志）
- [ ] 所有 data-testid 已按规范添加
- [ ] 快捷回复按钮正确解析 [y/n] 和数字选项
- [ ] 自定义输入框仅 Cmd+Enter 触发发送
- [ ] 发送确认对话框显示完整信息
