# 多环境配置

**类型**：基础设施
**负责人**：<!-- 待补充 -->
**最后更新**：2026-04-22
**别名**：多环境、env、环境隔离、TOML配置、配置加载

---

## 目标
> 为 ATWA 提供开发（development）、测试（test）、生产（production）三套完全隔离的环境配置，确保所有运行时产物（数据库、日志、PTY 录制文件、临时文件）收敛在 `~/.atwa/<env>/` 目录下，不会散落到系统其他位置。

## 范围
**包含：**
- 三环境目录规划与路径解析（`~/.atwa/<env>/`）
- TOML 分层配置机制（default.toml + 环境覆盖）
- 环境加载优先级（环境变量 > 启动参数 > 默认值）
- 日志规范（RotatingFileHandler + PTY 录制文件管理）
- 端口与进程冲突防护（pid 文件 + 端口隔离）
- 测试环境自动清理（conftest.py fixture）
- launchd plist 环境注入

**不包含：**
- 多机器/远程环境部署配置
- CI/CD 流水线配置
- 前端构建环境配置细节（仅约定 VITE_API_PORT 对接方式）

## 核心行为

### 变更内容
- 新增配置：
  - `config/default.toml` — 基准配置，定义所有字段的默认值
  - `config/development.toml` — 开发环境覆盖（更短轮询、DEBUG 日志、低告警阈值）
  - `config/test.toml` — 测试环境覆盖（隔离端口、最短超时、关闭 Insight Engine）
  - `config/production.toml` — 生产环境覆盖（保守配置、大连接池）
- 新增路径解析模块 `config/paths.py`
- 新增配置加载模块 `config/loader.py`（含 deep_merge + ATWA_OVERRIDE_ 环境变量覆盖）

### 影响范围
- 影响的服务 / 环境：daemon、server、前端（vite.config.ts 读取端口）
- 预期影响：所有运行时文件从散落状态收敛到 `~/.atwa/<env>/`，三环境端口互不冲突

### 各环境关键差异

| 配置项 | development | test | production |
|--------|------------|------|------------|
| Server 端口 | 8743 | 8744 | 8742 |
| 日志级别 | DEBUG | WARNING | INFO |
| 活跃轮询间隔 | 300ms | 100ms | 500ms |
| 空闲轮询间隔 | 1000ms | 500ms | 3000ms |
| idle_running 阈值 | 30s | 5s | 30s |
| 费用告警阈值 | $0.10 | — | $1.00 |
| Insight Engine | 开启 (min=2) | 关闭 | 开启 (min=5) |
| tmux socket | 默认 | atwa_test（隔离） | 默认 |
| DB 连接池 | 5 | 5 | 10 |

### 回滚方案
> 配置为纯文件变更，回滚只需恢复旧版 config/ 目录即可。数据库文件按环境隔离，不受影响。

### 上线步骤
1. 创建 `config/` 目录及四个 TOML 文件
2. 实现 `config/paths.py` 和 `config/loader.py`
3. 改造 daemon / server 启动入口，接入 `load_config()` 和 `get_paths()`
4. 添加 `conftest.py` 测试环境清理 fixture
5. 验证三环境独立启动无冲突

### 验证指标
- `~/.atwa/production/`、`~/.atwa/development/`、`~/.atwa/test/` 目录结构正确
- 三个环境可同时启动，端口互不冲突
- 配置加载优先级：ATWA_ENV > --env > 默认 production
- ATWA_OVERRIDE_* 环境变量可覆盖任意配置项
- 测试环境每次运行前自动清理

## 已知约束
- 所有路径必须通过 `config.paths` 获取，禁止硬编码
- 数据库文件路径由 `get_paths()` 动态计算，不写入 TOML
- `deep_merge` 为深度合并，不是浅覆盖
- PTY 录制文件名格式：`pane-<clean_id>.log`（去掉 % 前缀）
- 测试环境使用独立 tmux socket `atwa_test`，确保与开发/生产完全隔离

## 决策记录
> 关键设计决策和原因，变更时在此追加
- [2026-04-22] 初版：基于 `docs/02_多环境配置.md` 设计文档创建
