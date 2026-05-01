# 多环境配置 — Handoff Note

**日期**：2026-04-22
**状态**：进行中
**对应 Spec**：`docs/specs/multi-env-config.md`
**变更自**：
**PR / 分支**：<!-- 待补充 -->

---

## 背景
> ATWA 目前缺少环境隔离机制，开发和生产的数据库、日志、端口容易混用冲突。需要建立三套独立环境配置，让所有运行时产物收敛到 `~/.atwa/<env>/` 下。

## 本次交付范围
- 新增：`config/paths.py` — 路径解析模块
- 新增：`config/loader.py` — TOML 配置加载 + deep_merge + 环境变量覆盖
- 新增：`config/default.toml`、`config/development.toml`、`config/test.toml`、`config/production.toml`
- 新增：测试环境清理 fixture（conftest.py）
- 修改：daemon / server 启动入口，接入新配置系统
- 修改：日志初始化，使用 `config.paths` 和 `config.log` 参数

## 重点说明
> - 设计文档 `docs/02_多环境配置.md` 已提供完整的 TOML 配置内容和 Python 代码骨架，实现时可直接参考
> - `deep_merge` 需要自行实现（标准库无此函数），注意要递归合并 dict 而非浅覆盖
> - 环境变量覆盖的 key 格式为 `ATWA_OVERRIDE_<SECTION>_<KEY>`，需要做类型转换（`_cast`）
> - 前端 `vite.config.ts` 通过 `VITE_API_PORT` 环境变量读取对应端口，无需从 TOML 生成 `.env`

## 开发记录
> 只追加，不改写。记录过程中的决策、变更、阻塞。
- [2026-04-22] 创建 Spec 和 Handoff Note，准备开始开发
- [2026-04-22] 完成基础 config 模块实现：paths.py、loader.py、四个 TOML 文件、__init__.py、pyproject.toml。28 个测试全部通过。修复了 ATWA_OVERRIDE_ 环境变量对含下划线 section 名（如 insight_engine）的解析问题——改为从右往左尝试各 split 点匹配已知 section
- [2026-04-27] server/main.py 加入 PID 防重复启动逻辑：启动时检查 PID 文件是否指向存活进程，存活则拒绝启动，过期则清理；正常退出时清理 PID 文件。补全验收清单 #7 的 Python 层缺失

## 验收清单
- [x] `config/paths.py` — `get_paths()` 返回正确的目录结构，`ensure_dirs()` 可自动创建目录
- [x] `config/loader.py` — `load_config()` 按优先级正确加载（default → env → ATWA_OVERRIDE_）
- [x] `config/default.toml` 四个文件内容与设计文档一致
- [x] 三环境可同时启动，端口无冲突（8742/8743/8744）
- [x] 日志文件收敛在 `~/.atwa/<env>/logs/` 下
- [x] PTY 录制文件收敛在 `~/.atwa/<env>/logs/pty/` 下
- [x] pid 文件收敛在 `~/.atwa/<env>/tmp/` 下，启动检查防重复（Python 层 `server/main.py` + shell 层 `scripts/dev` 双重保护）
- [x] 测试环境 fixture 每次运行前清理 `~/.atwa/test/`（session-scoped 库/日志清理 + function-scoped 环境变量隔离）
- [x] deep_merge 为深度递归合并，非浅覆盖
- [x] ATWA_OVERRIDE_* 环境变量覆盖生效且类型正确
