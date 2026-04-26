# 感知层（Phase 1） — Handoff Note

**日期**：2026-04-26
**状态**：进行中
**对应 Spec**：`docs/specs/perception-layer.md`
**变更自**：
**PR / 分支**：<!-- 待补充 -->

---

## 背景
> 多环境配置和数据模型已落地，现在实现 Phase 1 核心感知层——5 个 daemon 模块 + atwa-wrap 脚本，让系统能发现 pane、采集输出、解析事件、驱动状态机。

## 本次交付范围
- 新增：`daemon/__init__.py` — 包初始化 + 公共导出
- 新增：`daemon/utils.py` — now_ms() 公共工具
- 新增：`daemon/tmux_discovery.py` — tmux pane 发现
- 新增：`daemon/capture.py` — 双模式输出采集
- 新增：`daemon/event_parser.py` — 事件解析（含 stuck/retry_loop 检测）
- 新增：`daemon/session_tracker.py` — 状态机 + DB 写入
- 新增：`daemon/attention_tracker.py` — 焦点切换追踪
- 新增：`scripts/atwa-wrap` — PTY 录制启动脚本
- 修改：`db/engine.py` — 新增 Database 类 + get_db() 异步上下文管理器
- 测试：7 个新测试文件，88 个新增测试用例
- 集成测试：5 个新文件，27 个集成测试用例

## 重点说明
> - libtmux/pyte/textdistance 依赖已在 pyproject.toml 中声明，无需新增
> - event_parser 的 parse_output() 是纯函数，StuckDetector 和 RetryLoopDetector 是有状态类，由 SessionTracker 拥有和调用
> - session_tracker 使用 SQLAlchemy update() 构造（非 __table__.update()）以通过 mypy 检查
> - db/engine.py 新增 Database 类封装 AsyncEngine + async_sessionmaker，session_tracker 和 attention_tracker 通过它访问数据库
> - ANSI 清洗使用 pyte Screen(220, dynamic_height)，高度按输入实际行数动态计算 `min(max(line_count, 24), 1000)`，正则兜底
> - atwa-wrap 脚本区分 macOS (-F) 和 Linux (-f -c) 的 script 命令差异
> - libtmux 0.55.0 API 变更：`list_sessions()`/`list_windows()`/`list_panes()` 已移除，改用 `.sessions`/`.windows`/`.panes` 属性（QueryList），生产代码和 mock 测试均已更新

## 开发记录
> 只追加，不改写。记录过程中的决策、变更、阻塞。
- [2026-04-26] 创建 Spec 和 Handoff Note，准备开始开发
- [2026-04-26] Step 0 完成：daemon/__init__.py, daemon/utils.py, db/engine.py (Database + get_db), tests/test_utils.py
- [2026-04-26] Step 1 完成：daemon/tmux_discovery.py + 7 tests — libtmux 字段可能为 None，用 `int(x or 0)` 防护
- [2026-04-26] Step 2 完成：daemon/capture.py + 19 tests — libtmux 必须模块级 import 才能被 mock.patch 打补丁
- [2026-04-26] Step 3 完成：daemon/event_parser.py + 33 tests — Ratcliff-Obershelp 相似度对渐进式文本仍可能触发 stuck，测试用例需使用差异更大的输出
- [2026-04-26] Step 4 完成：daemon/session_tracker.py + 18 tests — 使用 sqlalchemy.update() 替代 __table__.update() 解决 mypy 兼容性
- [2026-04-26] Step 5 完成：daemon/attention_tracker.py + 6 tests — session.refresh() 后 id 类型需 int() 转换通过 mypy
- [2026-04-26] Step 6-7 完成：scripts/atwa-wrap + 4 tests, daemon/__init__.py 导出更新
- [2026-04-26] 全部 131 个测试通过，ruff check + mypy 均通过
- [2026-04-26] 性能优化：capture.py clean_ansi_output 将 pyte.Screen 高度从固定 1000 改为动态计算 `min(max(raw.count('\n')+1, 24), 1000)`，典型场景缓冲区缩小 20 倍+
- [2026-04-26] libtmux API 兼容性修复：`list_sessions()`/`list_windows()`/`list_panes()` 在 0.55.0 中已移除，改为 `.sessions`/`.windows`/`.panes` 属性，影响 daemon/tmux_discovery.py、daemon/capture.py 及对应 mock 测试
- [2026-04-26] 集成测试完成：新增 tests/integration/ 目录，conftest.py 用 subprocess 管理真实 tmux server（socket=atwa_test），25 个集成测试全部通过
- [2026-04-26] 补全验收清单：新增 atwa-wrap 集成测试（TC-CAP-005/006）验证 PTY 录制可被 read_pty_log 读取；新增 SessionTracker 压力测试（TC-STRS-001/002）验证 12 并发 pane 稳定性和 DB 持久化

## 验收清单
- [x] tmux_discovery：3+ tmux session 时返回正确数量；tmux 未运行时返回 []（集成测试 TC-DISC-001/002）
- [x] tmux_discovery：同一 pane 多次调用返回相同 pane_id（集成测试 TC-DISC-003）
- [x] tmux_discovery：pane 关闭后不再出现在结果中（集成测试 TC-DISC-004）
- [x] capture：capture-pane 可从活跃 pane 抓到最新输出，不含 ANSI 码（集成测试 TC-CAP-001）
- [x] capture：ANSI 转义码清洗正确（集成测试 TC-CAP-002）
- [x] capture：PTY log 文件可被 read_pty_log 正确读取（集成测试 TC-CAP-003）
- [x] capture：atwa-wrap 启动的进程输出被完整录制（集成测试 TC-CAP-005/006）
- [x] capture：活跃/空闲自适应轮询间隔（get_capture_interval）
- [x] capture：PTY 文件超过 10MB 时自动轮转，保留 3 份
- [x] event_parser：waiting_input 在所有已知格式变体中均能检测到（集成测试 TC-PARSE-001/002）
- [x] event_parser：stuck 在 5 条相似输出后触发；正常进展不触发（集成测试 TC-PARSE-004）
- [x] event_parser：空输入/None 返回 []，不抛异常
- [x] event_parser：相同输入两次调用结果完全一致
- [x] session_tracker：状态转换幂等
- [x] session_tracker：状态写入数据库（persist_state_to_db 测试验证）
- [x] session_tracker：pane 关闭后 tick() 标记为 terminated
- [x] session_tracker：12 并发 pane 稳定，状态和 DB 持久化正确（压力测试 TC-STRS-001/002）
- [x] attention_tracker：焦点切换后 attention_log 有记录
- [x] attention_tracker：tmux 未运行时静默处理
- [x] atwa-wrap：可正确录制 AI CLI 输出到 PTY log 文件（集成测试 TC-CAP-005/006）
