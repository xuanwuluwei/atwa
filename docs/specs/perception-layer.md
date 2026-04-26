# 感知层（Phase 1）

**类型**：其他
**负责人**：<!-- 待补充 -->
**最后更新**：2026-04-26
**别名**：感知层、perception、tmux监控、pane状态、事件解析

---

## 目标
> 为 ATWA 构建感知层，实时发现和监控所有 tmux pane，采集输出、解析事件、驱动状态机、记录焦点切换，为后续 Insight Engine 和干预层提供数据基础。

## 范围
**包含：**
- `daemon/tmux_discovery.py` — 发现所有 tmux pane，返回 PaneInfo 列表
- `daemon/capture.py` — 双模式采集输出（capture-pane + PTY log）
- `daemon/event_parser.py` — 解析清洁文本为结构化 ParsedEvent
- `daemon/session_tracker.py` — 维护状态机，驱动 status 转换，写入数据库
- `daemon/attention_tracker.py` — 记录开发者焦点切换，写入 attention_log
- `scripts/atwa-wrap` — PTY 录制启动脚本

**不包含：**
- Web UI 渲染（Phase 1 后续步骤）
- Insight Engine 分析逻辑（Phase 2）
- 干预/自动恢复逻辑（Phase 3）
- 多 tmux server 的自动发现（仅支持 config 指定 socket）

## 核心行为

### 模块依赖关系
```
tmux_discovery → capture → event_parser → session_tracker → DB
                                                  ↕
                                        attention_tracker → DB
```

### tmux_discovery
- 使用 `libtmux.Server().list_sessions()` 枚举所有 session → window → pane
- 通过 `config.tmux.socket` 决定使用哪个 tmux server
- tmux 未运行时返回空列表，不抛异常
- 返回 `PaneInfo` 列表，包含 pane_id、session_name、window_index、pane_index、is_active、pid

### capture
- **capture-pane 模式**：轮询 `libtmux` 抓取，用于所有 pane 的活跃状态检测
- **PTY log 模式**：`atwa-wrap` 启动的 pane 有完整 tty 录制文件，数据更准确
- 采集参数从 `config.daemon` 读取：capture_interval_active_ms / idle_ms、scrollback_lines
- 活跃/空闲自适应轮询间隔
- 所有原始输出经 ANSI 清洗（pyte + 正则兜底）
- PTY 录制文件超过 10MB 时自动轮转，保留 3 份

### event_parser
- 纯函数模块，无状态，相同输入总产生相同输出
- 输入：pane_id + 清洁文本 → 输出：`ParsedEvent` 列表
- 检测 8 种事件类型：waiting_input、tool_start、tool_end、error、completed、token_usage、stuck、retry_loop
- stuck 检测使用 textdistance Ratcliff/Obershelp 相似度，窗口大小和阈值从配置读取
- retry_loop 检测：同一 tool_name + 相似参数在 60s 内出现 3+ 次
- 空输入、纯空白、None 均返回空列表，不抛异常

### session_tracker
- 维护所有 pane 的内存状态，基于 ParsedEvent 和时间阈值驱动状态机
- 状态转换幂等：同一事件重复处理不产生副作用
- 所有状态变更在 100ms 内写入数据库
- `tick()` 方法由 daemon 主循环定期调用，驱动基于时间的转换（idle/stuck/slow_tool）
- `get_attention_queue()` 按优先级排序返回需要处理的 pane 列表
- pane 关闭后，下一次 `tick()` 将其标记为 `terminated`

### attention_tracker
- 每 1 秒轮询当前焦点 pane（`tmux display-message`）
- 焦点切换时：结束上一个焦点记录，开始新焦点记录
- 焦点切换后 1.5 秒内在 `attention_log` 中有对应记录
- tmux 未运行时静默处理

### 注意力优先级排序
```
1. waiting_input   — agent 被阻塞，最高优先级
2. error_stopped   — 任务失败
3. stuck           — agent 陷入循环
4. cost_alert      — 费用超标
5. retry_loop      — 反复重试
6. slow_tool       — 工具调用缓慢
7. high_error_rate — 高错误率
```

### atwa-wrap 脚本
- 替代直接启动 AI CLI，用 `script -F` 录制完整 tty 输出
- 日志路径：`~/.atwa/<env>/logs/pty/pane-<clean_id>.log`
- 通过 `tmux display-message -p "#{pane_id}"` 获取当前 pane id

## 已知约束
- 所有阈值和可变参数必须从 `load_config()` 读取，禁止魔法数字
- 涉及 tmux 交互的函数必须优雅处理「tmux 未运行」的情况
- 数据库写入必须 try/except 保护，失败记录日志但不中断采集
- ANSI 清洗优先使用 pyte，正则兜底处理私有序列
- attention_log.pane_id 无外键（pane 可能已关闭）
- retry_loop 检测的状态由 event_parser 内部维护（纯函数接口外的内部状态）

## 决策记录
- [2026-04-26] 初版：基于 `docs/requirement/04_Phase1_感知层.md` 创建
