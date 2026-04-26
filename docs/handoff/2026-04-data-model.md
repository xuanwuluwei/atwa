# 数据模型（Phase 1 核心表） — Handoff Note

**日期**：2026-04-24
**状态**：进行中
**对应 Spec**：`docs/specs/data-model.md`
**变更自**：
**PR / 分支**：<!-- 待补充 -->

---

## 背景
> ATWA 需要 SQLite 数据库来存储 tmux pane 监控数据。多环境配置已完成（config 模块可用），数据库路径可由 `config.paths['db']` 获取，现在落地数据模型。

## 本次交付范围
- 新增：alembic 迁移框架（alembic.ini、migrations/env.py、migrations/versions/）
- 新增：初始迁移 — 创建 4 张核心表 + 索引
- 新增：数据库初始化模块 — 连接、PRAGMA 设置
- 集成：数据库路径使用 `config.paths['db']`

## 重点说明
> - 设计文档 `docs/requirement/03_数据模型.md` 提供了完整的 DDL，实现时可直接使用
> - `migrations/env.py` 中的数据库 URL 需要动态从 `config.loader.load_config()` + `config.paths.get_paths()` 获取
> - 所有时间戳为 Unix 毫秒整数（INTEGER），不用 DATETIME
> - attention_log 的 pane_id 不设外键，因为 pane 关闭后焦点记录仍需保留
> - Phase 2+ 表本次不实现，但迁移框架需为后续加表留好扩展点
> - SQLAlchemy 用 `Float` 而非 `Real`（设计文档写的是 REAL，但 SQLAlchemy 无 Real 类型）
> - `migrations/env.py` 中自动 `db_path.parent.mkdir(parents=True, exist_ok=True)` 确保目录存在
> - alembic 使用 aiosqlite 异步驱动，env.py 中 `run_migrations_online` 通过 asyncio.run 执行异步迁移

## 开发记录
> 只追加，不改写。记录过程中的决策、变更、阻塞。
- [2026-04-24] 创建 Spec 和 Handoff Note，准备开始开发
- [2026-04-24] 实现完成：db/models.py（4 个 ORM 模型）、db/engine.py（异步引擎 + PRAGMA）、alembic.ini + migrations/env.py + 001_initial_tables.py（初始迁移）、tests/test_db.py（13 个测试）
- [2026-04-24] SQLAlchemy 无 `Real` 类型，改用 `Float` 映射 SQLite REAL
- [2026-04-24] 修复 PRAGMA 事件监听注册方式：使用 `sqlalchemy.event.listens_for` 而非 `engine.sync_engine.event.listens_for`
- [2026-04-24] 测试使用 tmp_path 隔离，避免共享 SQLite 文件导致表重复创建
- [2026-04-24] `ATWA_ENV=test alembic upgrade head` 和 `ATWA_ENV=development alembic upgrade head` 均验证通过
- [2026-04-24] 所有 41 个测试通过（28 config + 13 db），无回归

## 验收清单
- [x] alembic.ini 配置正确，script_location 指向 migrations/
- [x] migrations/env.py 能根据 ATWA_ENV 动态获取数据库 URL
- [x] 初始迁移创建 4 张核心表，DDL 与设计文档一致
- [x] 索引正确创建（tool_events 两处、interventions 一处、attention_log 一处）
- [x] 外键约束正确：tool_events / interventions 引用 pane_sessions，ON DELETE CASCADE
- [x] attention_log.pane_id 无外键
- [x] 数据库连接时执行 PRAGMA（WAL / foreign_keys / busy_timeout）
- [x] 数据库路径来自 config.paths['db']，与环境配置集成
- [x] `ATWA_ENV=development alembic upgrade head` 可正常建表
- [x] `ATWA_ENV=test alembic upgrade head` 可正常建表
