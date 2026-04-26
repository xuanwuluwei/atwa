# ATWA 设计文档 — 05 Phase 1 服务层与前端

> 覆盖内容：FastAPI REST 接口、WebSocket 实时推送、Web UI 规范、iTerm2 跳转与内联输入、Phase 1 端到端验收标准。

---

## 1. FastAPI Server（server/main.py）

### 进程启动

Server 进程通过 launchd plist 启动，读取环境配置后绑定对应端口：

```python
# server/main.py
from config.loader import load_config
from config.paths import get_paths, ensure_dirs

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    ensure_dirs(cfg["env"]["name"])
    setup_logging(cfg["env"]["name"])
    yield

app = FastAPI(lifespan=lifespan)
```

---

## 2. REST 接口规范

### 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 返回所有 pane session（含 runtime_info） |
| GET | `/api/sessions/:pane_id` | 单个 session 详情 |
| PATCH | `/api/sessions/:pane_id` | 更新 display_name / description / tags |
| GET | `/api/sessions/:pane_id/events` | 该 session 的工具调用事件列表 |
| POST | `/api/sessions/:pane_id/send` | 通过 tmux send-keys 发送输入 |
| POST | `/api/sessions/:pane_id/focus` | 在 iTerm2 中聚焦到对应 pane |
| GET | `/api/insights` | 获取 insight 列表（Phase 3+） |
| PATCH | `/api/insights/:id` | 接受 / snooze / 忽略 insight |

### PATCH /api/sessions/:pane_id

```python
class SessionMetadataUpdate(BaseModel):
    display_name: str | None = None
    description:  str | None = None
    tags:         list[str] | None = None

@router.patch("/api/sessions/{pane_id}")
async def update_session_metadata(pane_id: str, body: SessionMetadataUpdate):
    # 只更新非 None 字段
    # 必须 await db.commit()，SQLAlchemy async 不自动提交
```

### POST /api/sessions/:pane_id/send

```python
class SendKeysRequest(BaseModel):
    text:    str
    confirm: bool = False  # False = dry-run，不实际执行

class SendKeysResponse(BaseModel):
    sent_at:  int | None    # 实际发送时间戳，dry-run 时为 None
    dry_run:  bool
    pane_id:  str

@router.post("/api/sessions/{pane_id}/send")
async def send_keys(pane_id: str, body: SendKeysRequest):
    # 验证 pane 存在，不存在返回 404
    # dry-run 时不调用 tmux，不写 interventions 表
    # 实际发送：tmux send-keys -t <pane_id> "<text>" Enter
    # 写入 interventions 表，包含 context_snapshot
```

### POST /api/sessions/:pane_id/focus

```python
@router.post("/api/sessions/{pane_id}/focus")
async def focus_pane(pane_id: str):
    session = await get_session(pane_id)
    if not session:
        raise HTTPException(404)

    host_app = session.host_app or "iterm2"

    # 1. tmux 切换到对应 pane
    subprocess.run(["tmux", "select-window", "-t",
                    f"{session.tmux_session}:{session.tmux_window}"])
    subprocess.run(["tmux", "select-pane", "-t", pane_id])

    # 2. 根据 host_app 决定 app 激活方式
    if host_app == "iterm2":
        subprocess.run(["osascript", "-e",
                        'tell application "iTerm2" to activate'])
    elif host_app == "vscode":
        # VSCode AppleScript 支持有限，只能激活窗口
        subprocess.run(["osascript", "-e",
                        'tell application "Visual Studio Code" to activate'])
        # 返回降级提示，前端展示给用户
        return {"degraded": True,
                "message": f"VSCode 终端暂不支持自动跳转，请手动切换到："
                           f"{session.tmux_session}:{session.tmux_window}.{session.tmux_pane}"}

    return {"focused": True, "pane_id": pane_id}
```

---

## 3. WebSocket 实时推送（server/ws.py）

### 协议规范

**连接路径**：`WS /ws/sessions`

**连接后立即推送初始状态**：

```json
{
  "type": "initial_state",
  "sessions": [ /* 全部 pane session 数组 */ ],
  "timestamp": 1714000000000
}
```

**状态变更推送**（每次 pane status 变化时）：

```json
{
  "type": "session_update",
  "pane_id": "%23",
  "status": "waiting_input",
  "status_reason": "Continue? [y/n]",
  "runtime_info": { /* 见 07_运行时信息与开发规范.md */ },
  "timestamp": 1714000000000
}
```

### 广播实现要点

```python
class WebSocketBroadcaster:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def broadcast(self, message: dict) -> None:
        """
        无客户端时立即返回，不阻塞。
        单个客户端发送失败时从集合移除，继续广播其他客户端。
        """
        if not self._clients:
            return
        dead = set()
        data = json.dumps(message)
        for ws in self._clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead
```

### 前端重连逻辑

```typescript
// frontend/src/hooks/useWebSocket.ts
function useWebSocket(url: string) {
  useEffect(() => {
    let ws: WebSocket
    let retryDelay = 1000

    function connect() {
      ws = new WebSocket(url)
      ws.onopen = () => { retryDelay = 1000 }
      ws.onclose = () => {
        setTimeout(connect, Math.min(retryDelay, 30000))
        retryDelay *= 2   // 指数退避，最长 30s
      }
      ws.onmessage = (e) => dispatch(JSON.parse(e.data))
    }

    connect()
    return () => ws.close()
  }, [url])
}
```

---

## 4. Web UI 规范

### 4.1 Session Card 结构

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

### 4.2 快捷回复逻辑

前端自动解析 agent 提示类型，展示对应快捷按钮：

| 提示类型 | 展示按钮 |
|----------|---------|
| `[y/n]` / `(y/N)` 格式 | `[✓ Yes]` `[✗ No]` |
| 数字选项 `(1-3)` | `[1]` `[2]` `[3]`（解析选项数量） |
| 任意输入 | 仅显示自定义输入框 |

### 4.3 输入发送安全规则

1. 自定义输入框必须按 **Cmd+Enter** 才触发，普通 Enter 不发送
2. 所有发送操作弹出确认对话框，显示：目标 pane 的 display_name、当前状态、将要发送的完整文本
3. 发送成功后，卡片显示「已发送: xxx」回显，10 秒后自动消失
4. dry-run 模式（`confirm: false`）可用于预览，不实际执行

### 4.4 内联编辑规则

- `display_name`：点击进入 input 框，Enter 保存，Escape 取消
- `description`：点击进入 textarea，失焦（blur）自动保存
- `tags`：点击 `[+]` 添加，点击已有 tag 删除
- 所有编辑立即调用 `PATCH /api/sessions/:pane_id`，不需要额外「保存」按钮

### 4.5 Status Badge 颜色映射

| 颜色 | 状态码 |
|------|-------|
| 🔴 红色 `status-red` | waiting_input / error_stopped / cost_alert / stuck |
| 🟠 橙色 `status-orange` | retry_loop / slow_tool / high_error_rate |
| 🟡 黄色 `status-yellow` | active / tool_executing / thinking |
| 🔵 蓝色 `status-blue` | waiting_tool / idle_running |
| 🟢 绿色 `status-green` | completed / idle_long / terminated |
| ⚫ 黑色 `status-black` | crashed / killed |

### 4.6 过滤器

顶部过滤栏：`ALL` / `NEED ATTENTION` / `RUNNING` / `DONE` / `DEAD`

- `NEED ATTENTION` 包含：waiting_input、error_stopped、cost_alert、stuck、retry_loop、slow_tool、high_error_rate
- `RUNNING` 包含：active、tool_executing、thinking、waiting_tool、idle_running
- `DONE` 包含：completed、idle_long、terminated
- `DEAD` 包含：crashed、killed

---

## 5. data-testid 规范

所有可交互的 UI 元素必须添加 `data-testid` 属性，供 E2E 测试使用，重构时不得删除：

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

---

## 6. Phase 1 端到端验收标准

以下标准全部通过才视为 Phase 1 完成：

1. Dashboard 在 2 秒内加载完成，显示所有当前 tmux pane
2. 状态变更通过 WebSocket 在 1 秒内推送到 UI
3. 从 UI 发送 "y" 后，tmux pane 正确收到该输入
4. Focus 按钮点击后，iTerm2 切换到对应 pane 并置前
5. display_name / description / tags 编辑后页面刷新仍然保留
6. 系统在 10+ 并发 pane 下稳定运行
7. tmux pane 被关闭时，系统在 2 个 poll 周期内将其标记为 terminated
8. Daemon 崩溃重启后，Server 继续提供历史数据，不丢失已收集的状态
9. 无 JS 控制台错误（开发模式下 0 个 error 级别日志）
