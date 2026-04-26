# 数据模型（Phase 1 核心表）

**类型**：数据变更
**负责人**：<!-- 待补充 -->
**最后更新**：2026-04-24
**别名**：数据模型、database、schema、SQLite

---

## 目标
> 为 ATWA 建立单一 SQLite 数据库，存储 tmux pane 监控的核心数据，支撑状态追踪、工具调用分析和开发者干预记录。

## 范围
**包含：**
- 数据库初始化（WAL 模式、foreign_keys、busy_timeout）
- `pane_sessions` 表 — pane 生命周期信息
- `tool_events` 表 — 工具调用详细记录
- `interventions` 表 — 开发者干预行为
- `attention_log` 表 — tmux 焦点切换历史
- alembic 迁移框架搭建 + 初始迁移
- 与多环境配置的集成（数据库路径由 config 决定）

**不包含：**
- Phase 2+ 表（session_summaries、skill_patterns、skill_usage、insights、session_embeddings）
- sqlite-vec 扩展加载
- ORM 查询接口 / Repository 层
- 数据写入的业务逻辑（由 PTY 监控等上层模块负责）

## 核心行为

### 数据库位置
路径由环境配置决定（`config.paths['db']`），对应 `~/.atwa/<env>/atwa.db`。

### 初始化 PRAGMA
```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 30000;   -- 对应 config.database.timeout_s
```

### 核心表结构

**pane_sessions**：tmux pane 生命周期
- `pane_id TEXT PRIMARY KEY` — tmux pane 唯一 id，格式 `%NN`
- `tmux_session / tmux_window / tmux_pane` — tmux 定位三要素
- `display_name / description / tags` — 用户自定义元数据（tags 为 JSON 数组字符串）
- `agent_type / host_app` — 分类字段
- `status TEXT NOT NULL` — 状态枚举（见下方），`status_reason` 为补充说明
- `started_at / ended_at / last_output_at` — 时间戳（Unix 毫秒整数）
- `token_input / token_output / cost_usd` — 用量统计
- `created_at / updated_at` — 记录级时间戳

**tool_events**：工具调用记录
- `pane_id` 外键引用 pane_sessions（ON DELETE CASCADE）
- `tool_name / started_at / ended_at / duration_ms` — 调用基本信息
- `status` — running | success | error
- `error_summary` — 错误信息前 200 字符
- `raw_snippet` — 原始输出片段前 500 字符
- 索引：`pane_id`、`started_at DESC`

**interventions**：开发者干预
- `pane_id` 外键引用 pane_sessions（ON DELETE CASCADE）
- `type` — input | correction | kill | restart | skip
- `content` — 发送内容或操作描述
- `context_snapshot` — 干预前 agent 输出最后 500 字符
- 索引：`pane_id`

**attention_log**：焦点切换
- `pane_id` 无外键（pane 可能已关闭）
- `started_at / ended_at / duration_ms` — 焦点时段
- 索引：`pane_id`

### Status 枚举（pane_sessions.status）
优先级从高到低：
- 🔴 waiting_input > error_stopped > cost_alert > stuck
- 🟠 retry_loop > slow_tool > high_error_rate
- 🟡 active > tool_executing > thinking
- 🔵 waiting_tool > idle_running
- 🟢 completed > idle_long > terminated
- ⚫ crashed > killed

### Schema 迁移
- 使用 alembic 管理，迁移文件存放 `migrations/versions/`
- 数据库 URL 由运行时配置注入，通过 `migrations/env.py` 动态获取
- 迁移命令需指定 `ATWA_ENV` 环境变量

## 已知约束
- 所有时间戳为 Unix 毫秒整数，不使用 ISO 字符串
- tags 字段存 JSON 字符串，不使用独立的 tag 关联表
- attention_log 不设外键，因为 pane 关闭后记录仍需保留
- SQLite 单文件，不支持并发写入（依赖 WAL + busy_timeout）

## 决策记录
- [2026-04-24] 初版：Phase 1 仅包含 4 张核心表，Phase 2+ 表后续迭代
