# 服务层与前端（Phase 1）

**类型**：其他
**负责人**：<!-- 待补充 -->
**最后更新**：2026-04-27
**别名**：服务层、前端、FastAPI、WebSocket、Web UI、Dashboard、iTerm2跳转

---

## 目标
> 构建 ATWA 的服务层和 Web 前端，让开发者通过浏览器实时监控所有 tmux pane 状态，并通过 UI 直接输入指令、跳转终端，实现 Phase 1 端到端闭环。

## 范围
**包含：**
- `server/main.py` — FastAPI 应用入口 + lifespan 管理
- REST 接口：sessions CRUD、send-keys、focus、events 查询
- `server/ws.py` — WebSocket 实时推送（session 状态变更）
- Web UI：Session Dashboard（卡片列表、过滤、内联编辑、快捷回复、确认对话框）
- iTerm2 / VSCode 跳转（osascript）
- data-testid 规范（E2E 测试基础）
- Phase 1 端到端验收标准

**不包含：**
- Insight Engine 相关接口（Phase 3+）
- 用户认证 / 权限系统
- 移动端适配
- VSCode 终端的完整跳转支持（仅激活窗口，降级提示）
- 多 Server 实例部署

## 核心行为

### 模块依赖关系
```
daemon → DB ← server (REST + WS) → frontend
                                      ↕
                              tmux send-keys / osascript
```

### FastAPI Server

- 通过 launchd plist 启动，读取 `load_config()` 绑定对应端口
- lifespan 中完成配置加载、目录初始化、日志设置
- 与 daemon 共享同一数据库实例

### REST 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 返回所有 pane session（含 runtime_info） |
| GET | `/api/sessions/:pane_id` | 单个 session 详情 |
| PATCH | `/api/sessions/:pane_id` | 更新 display_name / description / tags |
| GET | `/api/sessions/:pane_id/events` | 该 session 的工具调用事件列表 |
| POST | `/api/sessions/:pane_id/send` | 通过 tmux send-keys 发送输入 |
| POST | `/api/sessions/:pane_id/focus` | 在 iTerm2 中聚焦到对应 pane |
| GET | `/api/insights` | 获取 insight 列表（Phase 3+，当前占位） |
| PATCH | `/api/insights/:id` | 接受 / snooze / 忽略 insight（Phase 3+） |

#### PATCH /api/sessions/:pane_id
- 请求体 `SessionMetadataUpdate`：display_name / description / tags，均为 Optional
- 只更新非 None 字段
- 必须 `await db.commit()`，SQLAlchemy async 不自动提交

#### POST /api/sessions/:pane_id/send
- 请求体 `SendKeysRequest`：text + confirm（默认 false = dry-run）
- 响应 `SendKeysResponse`：sent_at（dry-run 时 None）、dry_run、pane_id
- dry-run 时不调用 tmux，不写 interventions 表
- 实际发送：`tmux send-keys -t <pane_id> "<text>" Enter`
- 写入 interventions 表，包含 context_snapshot
- pane 不存在返回 404

#### POST /api/sessions/:pane_id/focus
- 先通过 tmux 命令切换到对应 window + pane
- 根据 session.host_app 决定激活方式：
  - `iterm2`：osascript 激活 iTerm2 → 返回 `{focused: true}`
  - `vscode`：osascript 激活 VSCode → 返回 `{degraded: true, message: "..."}`（降级提示）
- session 不存在返回 404

### WebSocket 实时推送

- 连接路径：`WS /ws/sessions`
- 连接后立即推送 `initial_state`（全部 session 数组 + timestamp）
- 状态变更时推送 `session_update`（pane_id、status、status_reason、runtime_info、timestamp）
- `WebSocketBroadcaster` 维护客户端集合，无客户端时立即返回
- 单个客户端发送失败时从集合移除，继续广播其他客户端
- 前端重连：指数退避（1s → 2s → 4s → …，最长 30s）

### Web UI — Session Card 结构

```
┌──────────────────────────────────────────────────────────┐
│ 🔴  [claude-agent-3 ✎]        waiting_input  ⏱ 12m34s   │
│     重构 API 认证模块               [backend] [auth]      │
├──────────────────────────────────────────────────────────┤
│ [waiting_input 时自动展开]                                │
│ Agent: "Found 3 errors, continue anyway? [y/n]"          │
│                                                          │
│ 快捷回复：  [✓ Yes]  [✗ No]                              │
│ ┌─────────────────────────────────────────── [Cmd+↵] ┐   │
│ │ 或直接输入...                                       │   │
│ └─────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────┤
│ 运行时：tool_executing · Write · step 7   tok:8k $0.12  │
│                              [↗ 跳转 iTerm2]  [展开 ∨]  │
└──────────────────────────────────────────────────────────┘
```

### 快捷回复逻辑

| 提示类型 | 展示按钮 |
|----------|---------|
| `[y/n]` / `(y/N)` 格式 | `[✓ Yes]` `[✗ No]` |
| 数字选项 `(1-3)` | `[1]` `[2]` `[3]`（解析选项数量） |
| 任意输入 | 仅显示自定义输入框 |

### 输入发送安全规则

1. 自定义输入框必须按 **Cmd+Enter** 才触发，普通 Enter 不发送
2. 所有发送操作弹出确认对话框，显示：目标 pane 的 display_name、当前状态、将要发送的完整文本
3. 发送成功后，卡片显示「已发送: xxx」回显，10 秒后自动消失
4. dry-run 模式（`confirm: false`）可用于预览，不实际执行

### 内联编辑规则

- `display_name`：点击进入 input 框，Enter 保存，Escape 取消
- `description`：点击进入 textarea，失焦（blur）自动保存
- `tags`：点击 `[+]` 添加，点击已有 tag 删除
- 所有编辑立即调用 `PATCH /api/sessions/:pane_id`，不需要额外「保存」按钮

### Status Badge 颜色映射

| 颜色 | 状态码 |
|------|-------|
| 🔴 红色 `status-red` | waiting_input / error_stopped / cost_alert / stuck |
| 🟠 橙色 `status-orange` | retry_loop / slow_tool / high_error_rate |
| 🟡 黄色 `status-yellow` | active / tool_executing / thinking |
| 🔵 蓝色 `status-blue` | waiting_tool / idle_running |
| 🟢 绿色 `status-green` | completed / idle_long / terminated |
| ⚫ 黑色 `status-black` | crashed / killed |

### 过滤器

顶部过滤栏：`ALL` / `NEED ATTENTION` / `RUNNING` / `DONE` / `DEAD`

- `NEED ATTENTION`：waiting_input、error_stopped、cost_alert、stuck、retry_loop、slow_tool、high_error_rate
- `RUNNING`：active、tool_executing、thinking、waiting_tool、idle_running
- `DONE`：completed、idle_long、terminated
- `DEAD`：crashed、killed

### data-testid 规范

所有可交互 UI 元素必须添加 `data-testid`，重构时不得删除：

| 元素 | data-testid |
|------|-------------|
| 整个 Dashboard | `dashboard` |
| Dashboard Header | `dashboard-header` |
| Session 列表容器 | `session-list` |
| 过滤栏 | `filter-bar` |
| 单个 Session Card | `session-card`（+ `data-pane-id`） |
| 状态徽章 | `status-badge` |
| display-name 文本 | `display-name` |
| display-name 输入框 | `display-name-input` |
| description 文本 | `description` |
| 计时器 | `elapsed-timer` |
| 当前工具名 | `current-tool` |
| Token 数量 | `token-count` |
| 输入区域 | `input-area` |
| Agent 提示文本 | `agent-prompt` |
| 快捷回复 Yes | `quick-reply-yes` |
| 快捷回复 No | `quick-reply-no` |
| 自定义输入框 | `custom-input` |
| 发送确认对话框 | `send-confirm-dialog` |
| 确认内容预览 | `confirm-preview` |
| 确认目标 | `confirm-target` |
| 跳转 iTerm2 按钮 | `focus-btn` |
| 展开按钮 | `expand-btn` |
| 工具历史 | `tool-history` |
| WS 连接状态 | `ws-status` |
| Insight Badge | `insight-badge` |
| Insight Panel | `insight-panel` |
| 单条 Insight | `insight-item` |
| 错误提示 Banner | `error-banner` |
| 重试按钮 | `retry-btn` |

### Phase 1 端到端验收标准

1. Dashboard 在 2 秒内加载完成，显示所有当前 tmux pane
2. 状态变更通过 WebSocket 在 1 秒内推送到 UI
3. 从 UI 发送 "y" 后，tmux pane 正确收到该输入
4. Focus 按钮点击后，iTerm2 切换到对应 pane 并置前
5. display_name / description / tags 编辑后页面刷新仍然保留
6. 系统在 10+ 并发 pane 下稳定运行
7. tmux pane 被关闭时，系统在 2 个 poll 周期内将其标记为 terminated
8. Daemon 崩溃重启后，Server 继续提供历史数据，不丢失已收集的状态
9. 无 JS 控制台错误（开发模式下 0 个 error 级别日志）

## 已知约束
- 前端技术栈：TypeScript / React / Vite（项目 CLAUDE.md 已指定）
- 时间戳统一用 Unix 毫秒整数
- 所有新增 public 函数必须有类型标注
- 涉及 tmux 交互的函数必须优雅处理「tmux 未运行」的情况
- 数据库写入必须 try/except 保护
- 单文件不超过 500 行
- VSCode 终端跳转为降级方案（仅激活窗口，不自动跳转到具体 pane）
- Insight 相关接口为 Phase 3+ 占位，当前仅预留路由

## 决策记录
- [2026-04-27] 初版：基于 `docs/requirement/05_Phase1_服务层与前端.md` 创建
