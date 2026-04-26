# ATWA 设计文档 — 04 Phase 1 感知层

> Phase 1 目标：可运行的系统，监控所有 tmux pane、分类状态、渲染实时 Web UI。本文档覆盖感知层的 5 个模块。

---

## 1. 模块总览

| 模块文件 | 职责 |
|----------|------|
| `daemon/tmux_discovery.py` | 发现所有 tmux pane，返回 PaneInfo 列表 |
| `daemon/capture.py` | 双模式采集输出：capture-pane + PTY log |
| `daemon/event_parser.py` | 解析清洁文本，输出结构化 ParsedEvent |
| `daemon/session_tracker.py` | 维护状态机，驱动 status 转换，写入数据库 |
| `daemon/attention_tracker.py` | 记录开发者焦点切换，写入 attention_log |

---

## 2. tmux Discovery（daemon/tmux_discovery.py）

### 职责

枚举 tmux server 下所有 session → window → pane，返回 `PaneInfo` 列表。处理多 tmux server（`-L socket` 参数）的场景。

### 接口契约

```python
from typing import TypedDict

class PaneInfo(TypedDict):
    pane_id:      str   # %23，tmux 分配的唯一 id，进程生命周期内稳定
    session_name: str   # "agents"
    window_index: int   # 0
    pane_index:   int   # 1
    is_active:    bool  # 当前是否为焦点 pane
    pid:          int   # pane 内 shell 进程的 PID

def discover_all_panes() -> list[PaneInfo]:
    """
    使用 libtmux.Server().list_sessions() 枚举。
    tmux 未运行时返回空列表（不抛出异常）。
    通过 config.tmux.socket 决定使用哪个 tmux server。
    """
```

### 关键实现细节

```python
import libtmux
from config.loader import load_config

def discover_all_panes() -> list[PaneInfo]:
    cfg = load_config()
    socket = cfg["tmux"]["socket"] or None   # 空字符串转为 None（使用默认 socket）
    try:
        server = libtmux.Server(socket_name=socket)
        result = []
        for session in server.list_sessions():
            for window in session.list_windows():
                for pane in window.list_panes():
                    result.append(PaneInfo(
                        pane_id=pane.pane_id,
                        session_name=session.name,
                        window_index=int(window.window_index),
                        pane_index=int(pane.pane_index),
                        is_active=(pane.pane_active == "1"),
                        pid=int(pane.pane_pid),
                    ))
        return result
    except Exception as e:
        logger.warning(f"tmux server not found or inaccessible: {e}")
        return []
```

### 验收标准

- 3+ tmux session 时返回正确数量
- tmux 未运行时返回 `[]`，不抛出异常
- 同一 pane 多次调用返回相同 `pane_id`
- pane 关闭后下次调用不再出现在结果中

---

## 3. Output Capture（daemon/capture.py）

### 职责

双模式采集 tmux pane 输出：

- **capture-pane 模式**：轮询 `libtmux` 抓取，用于所有 pane 的活跃状态检测
- **PTY log 模式**：`atwa-wrap` 启动的 pane 有完整 tty 录制文件，数据更准确

### PTY Log 设置

用户用 `atwa-wrap` 启动 AI CLI：

```bash
# 替代：claude
# 使用：atwa-wrap claude

# atwa-wrap 内部使用 script 命令录制
# 日志路径：~/.atwa/<env>/logs/pty/pane-<id>.log
```

`scripts/atwa-wrap` 的核心逻辑：

```bash
#!/bin/bash
PANE_ID=$(tmux display-message -p "#{pane_id}")
CLEAN_ID="${PANE_ID#%}"
ENV="${ATWA_ENV:-production}"
LOG_FILE="$HOME/.atwa/$ENV/logs/pty/pane-$CLEAN_ID.log"
mkdir -p "$(dirname "$LOG_FILE")"
exec script -F "$LOG_FILE" "$@"
```

### 采集参数

通过 `config.daemon` 控制（见 `02_多环境配置.md`）：

```toml
capture_interval_active_ms = 500    # 活跃 pane（有近期输出）
capture_interval_idle_ms   = 3000   # 空闲 pane
scrollback_lines           = 200    # 每次 capture-pane 抓取行数
```

### ANSI 清洗

所有采集到的原始输出必须经过 pyte 清洗，去除颜色/光标等 ANSI 序列：

```python
import pyte

def clean_ansi_output(raw: str) -> str:
    screen = pyte.Screen(220, 50)
    stream = pyte.Stream(screen)
    stream.feed(raw)
    lines = [screen.draw(i) for i in range(screen.lines)]
    return "\n".join(line.rstrip() for line in lines if line.strip())
```

若 pyte 对私有序列处理不完整，加正则兜底：

```python
import re
def clean_ansi_output(raw: str) -> str:
    clean = re.sub(r'\x1b\[[0-9;]*[mGKHFJABCDsuhr]', '', raw)
    clean = re.sub(r'\x1b\][^\x07]*\x07', '', clean)   # OSC 序列
    return clean
```

### PTY log 轮转

PTY 录制文件使用 `RotatingFileHandler` 逻辑管理，所有文件收敛在 `~/.atwa/<env>/logs/pty/` 下：

```python
from config.paths import get_pty_log_path

def get_pty_log_path(pane_id: str, env: str) -> Path:
    """路径：~/.atwa/<env>/logs/pty/pane-<id>.log"""
    paths = get_paths(env)
    clean_id = pane_id.lstrip("%")
    return paths["pty_dir"] / f"pane-{clean_id}.log"
```

### 验收标准

- capture-pane 可从活跃 pane 抓到最新输出，不含 ANSI 码
- PTY log 模式下 `atwa-wrap` 启动的进程输出被完整录制
- 活跃/空闲自适应轮询间隔误差 ±100ms 以内
- PTY 文件超过 10MB 时自动轮转，保留 3 份

---

## 4. Event Parser（daemon/event_parser.py）

### 职责

将清洁文本解析为结构化 `ParsedEvent` 列表。**纯函数模块，无状态**，所有状态由调用方（SessionTracker）维护。

### 接口契约

```python
class ParsedEvent(TypedDict):
    pane_id:    str
    event_type: str       # 见下方检测规则
    timestamp:  int       # ms 时间戳
    data:       dict      # 事件类型特定的载荷
    confidence: float     # 0.0 - 1.0

def parse_output(pane_id: str, text: str) -> list[ParsedEvent]:
    """纯函数，相同输入总产生相同输出"""
```

### 检测规则

| 事件类型 | 检测模式 | 置信度 |
|----------|---------|--------|
| `waiting_input` | `[y/n]`、`(y/N)`、`Continue?`、`Input required`、`Enter your choice` | 高 |
| `tool_start` | `Tool: <名称>` / `Running <名称>` / `Using <名称>` | 高 |
| `tool_end` | 工具输出块边界（分隔线 + Output 标记） | 中 |
| `error` | `Error:`、`Exception:`、`Traceback`、`FAILED`、`exit code [1-9]` | 高 |
| `completed` | `Task complete`、`Done.`、`All tasks finished`、`✓ Complete` | 高 |
| `token_usage` | `Tokens: NNN` / `Usage: in:NNN out:NNN` | 高 |
| `stuck` | textdistance(最近5条输出) > `stuck_similarity` 阈值，连续 3 次触发 | 中 |
| `retry_loop` | 同一 tool_name + 相似参数在 60s 内出现 3+ 次 | 高 |

### stuck 检测实现

```python
import textdistance

class StuckDetector:
    def __init__(self, threshold: float, window_size: int):
        self.threshold = threshold
        self.window_size = window_size
        self._history: dict[str, list[str]] = {}   # pane_id -> 历史输出列表

    def update(self, pane_id: str, text: str) -> ParsedEvent | None:
        history = self._history.setdefault(pane_id, [])
        history.append(text)
        if len(history) > self.window_size:
            history.pop(0)
        if len(history) < self.window_size:
            return None

        # 计算窗口内所有相邻对的平均相似度
        similarities = [
            textdistance.ratcliff_obershelp(history[i], history[i+1])
            for i in range(len(history) - 1)
        ]
        avg_sim = sum(similarities) / len(similarities)

        if avg_sim >= self.threshold:
            return ParsedEvent(
                pane_id=pane_id,
                event_type="stuck",
                timestamp=now_ms(),
                data={"avg_similarity": avg_sim},
                confidence=min(avg_sim, 0.99),
            )
        return None
```

### 验收标准

- `waiting_input` 在所有已知格式变体中均能检测到
- `stuck` 在 5 条相似输出后触发；正常进展的输出不触发
- 空字符串、纯空白、`None` 输入均返回 `[]`，不抛出异常
- 相同输入两次调用结果完全一致（纯函数验证）

---

## 5. Session Tracker（daemon/session_tracker.py）

### 职责

维护所有 pane 的内存状态，基于 `ParsedEvent` 和时间阈值驱动状态机转换，将变更同步写入数据库。

### 时间阈值

所有阈值从配置读取（`config.thresholds`）：

```python
THRESHOLDS = {
    "idle_running_s": 30,    # active → idle_running
    "idle_long_s":    300,   # idle_running → idle_long
    "slow_tool_s":    180,   # tool_executing → slow_tool
    "stuck_window":   5,     # stuck detector 窗口大小
}
```

### 核心接口

```python
class SessionTracker:
    def upsert_pane(self, pane_info: PaneInfo) -> None:
        """注册或更新 pane，如已存在则跳过"""

    def process_event(self, event: ParsedEvent) -> None:
        """
        处理解析事件，触发状态转换。
        幂等：相同事件重复处理结果不变。
        所有状态变更在 100ms 内写入数据库。
        """

    def tick(self) -> None:
        """
        时间驱动检查：idle/stuck/slow_tool 等基于时间的转换。
        由 daemon 主循环定期调用。
        """

    def get_attention_queue(self) -> list[dict]:
        """
        返回所有 pane 的状态列表，按优先级排序。
        需要处理的 pane 排在前面。
        """

    def get_status(self, pane_id: str) -> str | None:
        """返回当前内存中的状态，pane 不存在时返回 None"""
```

### 注意力优先级排序

`get_attention_queue()` 按以下顺序排列需要处理的 pane：

```
1. waiting_input   — agent 被阻塞，最高优先级
2. error_stopped   — 任务失败
3. stuck           — agent 陷入循环
4. cost_alert      — 费用超标
5. retry_loop      — 反复重试
6. slow_tool       — 工具调用缓慢
7. high_error_rate — 高错误率
```

### 数据库写入规范

```python
async def _persist_status_change(self, pane_id: str, new_status: str, reason: str = ""):
    """
    状态变更必须在事件处理后 100ms 内落库。
    使用 try/except 保护，写入失败记录日志但不抛出（不能因为 DB 问题影响采集）。
    """
    try:
        async with get_db() as db:
            await db.execute(
                "UPDATE pane_sessions SET status=?, status_reason=?, updated_at=? WHERE pane_id=?",
                (new_status, reason, now_ms(), pane_id)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist status change for {pane_id}: {e}")
```

### 验收标准

- 状态转换幂等：同一事件重复处理不产生副作用
- 状态写入数据库延迟 <= 100ms
- pane 关闭后，下一次 `tick()` 将其标记为 `terminated`
- 10+ 并发 pane 时系统稳定，无状态混乱

---

## 6. Attention Tracker（daemon/attention_tracker.py）

### 职责

每 1 秒轮询当前焦点 pane（`tmux display-message`），记录焦点切换到 `attention_log` 表。这是 Phase 3 Insight Engine 判断开发者认知负载的基础数据。

### 核心逻辑

```python
class AttentionTracker:
    def __init__(self, db, cfg):
        self._current_pane_id: str | None = None
        self._focus_start: int = 0

    async def tick(self) -> None:
        """每 1 秒调用一次"""
        focused = self._get_focused_pane()
        if focused == self._current_pane_id:
            return

        now = now_ms()
        if self._current_pane_id:
            # 结束上一个焦点记录
            await self._end_focus(self._current_pane_id, self._focus_start, now)

        self._current_pane_id = focused
        self._focus_start = now
        if focused:
            await self._start_focus(focused, now)

    def _get_focused_pane(self) -> str | None:
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_id}"],
                capture_output=True, text=True, timeout=1
            )
            return result.stdout.strip() or None
        except Exception:
            return None
```

### 验收标准

- 焦点切换后 1.5 秒内在 `attention_log` 中有对应记录
- `ended_at` 和 `duration_ms` 正确填充
- tmux 未运行时静默处理，不写入异常记录
