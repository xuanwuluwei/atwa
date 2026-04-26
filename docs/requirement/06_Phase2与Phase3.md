# ATWA 设计文档 — 06 Phase 2 记忆层 & Phase 3 智能层

---

## Phase 2 — 记忆层

**目标**：建立统一的记忆存储，记录行为模式（结构化事件）和语义内容（Embedding），为 Phase 3 提供数据基础。

---

## 1. 结构化记忆（SQLite）

Phase 1 的所有表在 Phase 2 继续使用，Phase 2 新增以下补充表（见 `03_数据模型.md`）：

- `session_summaries`：session 结束后生成的自然语言摘要
- `skill_patterns`：工具序列重复模式记录
- `skill_usage`：Skill 使用效果跟踪
- `insights`：Insight Engine 生成的建议

### 1.1 Session Summary 生成

```python
# insight_engine/generator.py

async def generate_session_summary(pane_id: str, db) -> None:
    """
    在 session 结束后（status 变为 completed/terminated/crashed）触发。
    调用 Anthropic API 生成摘要，超时 30s，失败重试 2 次。
    """
    session = await db.get_session(pane_id)
    events = await db.get_tool_events(pane_id)
    interventions = await db.get_interventions(pane_id)

    prompt = f"""
    分析以下 AI agent 工作会话，输出 JSON：
    {{
      "summary_text": "300字以内的自然语言摘要",
      "key_decisions": ["决策1", "决策2"],
      "tool_sequence": [{{"tool": "Bash", "count": 5, "avg_ms": 2000}}]
    }}

    会话信息：
    - 工具调用序列：{json.dumps(events)}
    - 开发者干预：{json.dumps(interventions)}
    - 总耗时：{session.ended_at - session.started_at}ms
    """

    response = await anthropic_client.messages.create(
        model=cfg["insight_engine"]["anthropic_model"],
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    # 解析并写入 session_summaries 表
```

### 1.2 工具序列模式识别

```python
# daemon/pattern_recorder.py

def compute_pattern_hash(tool_sequence: list[str]) -> str:
    """
    将工具序列归一化（去重连续重复、转小写），计算哈希。
    例：["Bash", "Bash", "Read", "Write"] → "bash,read,write"
    """
    normalized = []
    for tool in tool_sequence:
        if not normalized or normalized[-1] != tool.lower():
            normalized.append(tool.lower())
    return hashlib.md5(",".join(normalized).encode()).hexdigest()

async def record_pattern(pane_id: str, db) -> None:
    """在 session 结束时调用，更新 skill_patterns 表"""
    events = await db.get_tool_events(pane_id)
    sequence = [e.tool_name for e in events]
    pattern_hash = compute_pattern_hash(sequence)

    existing = await db.get_pattern(pattern_hash)
    if existing:
        await db.increment_pattern(pattern_hash, pane_id)
    else:
        await db.create_pattern(pattern_hash, sequence, pane_id)
```

---

## 2. 语义记忆（sqlite-vec）

与结构化记忆共存于同一 SQLite 文件，无需额外部署。

### 2.1 Embedding 生成与存储

```python
# insight_engine/embeddings.py
from fastembed import TextEmbedding

# 模型一次性加载，避免重复初始化
_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")

async def store_session_embedding(pane_id: str, summary: dict, db) -> str:
    """
    将 summary_text + key_decisions + tool_sequence 合并为文本，
    生成 384 维 Embedding，存入 session_embeddings 虚拟表。
    返回 embedding_id（rowid 字符串）。
    """
    text = f"{summary['summary_text']} "
    text += " ".join(summary['key_decisions'])
    text += " ".join(t["tool"] for t in summary['tool_sequence'])

    embedding = list(_model.embed([text]))[0].tolist()
    rowid = await db.insert_embedding(embedding)
    return str(rowid)

async def find_similar_sessions(text: str, top_k: int = 5, db = None) -> list[str]:
    """
    向量相似度检索，返回最相似的 pane_id 列表。
    """
    embedding = list(_model.embed([text]))[0].tolist()
    results = await db.execute("""
        SELECT s.pane_id, vec_distance_cosine(e.embedding, ?) as distance
        FROM session_embeddings e
        JOIN session_summaries s ON s.embedding_id = e.rowid
        ORDER BY distance ASC
        LIMIT ?
    """, (embedding, top_k))
    return [row["pane_id"] for row in results]
```

### 2.2 ChromaDB 迁移路径

当 session 数量超过 2000 时，sqlite-vec 的检索性能可能下降，可迁移到 ChromaDB：

```python
# 迁移触发条件（在 insight_engine/embeddings.py 中检查）
async def check_migration_needed(db) -> bool:
    count = await db.scalar("SELECT COUNT(*) FROM session_summaries")
    return count > 2000

# 迁移时：从 session_embeddings 读取所有向量，批量写入 ChromaDB
# ChromaDB 同样以本地文件模式运行，路径：~/.atwa/<env>/chromadb/
```

---

## 3. Skill 生命周期

```
观察到重复模式（occurrence_count >= 3）
    ↓
suggested（occurrence_count >= 5 时创建 insight）
    ↓ 用户接受
draft（Anthropic API 生成 Skill 草稿 Markdown）
    ↓ 用户确认
active（加入 skill registry，开始记录 skill_usage）
    ↓ correction_count / usage_count > 0.3
degraded（创建 improve_skill insight）
    ↓ 30 天无使用
deprecated（创建 deprecate_skill insight）
```

| 阶段 | 触发条件 | 操作 |
|------|---------|------|
| observed | pattern_hash 出现 3+ 次 | 创建 skill_patterns 记录 |
| suggested | occurrence_count >= 5 | 创建 type=new_skill 的 insight |
| draft | 用户接受建议 | 调用 API 生成 Skill Markdown |
| active | 用户确认草稿 | 加入 skill registry |
| degraded | correction_count / usage_count > 0.3 | 创建 type=improve_skill 的 insight |
| deprecated | 30 天内无 skill_usage 记录 | 创建 type=deprecate_skill 的 insight |

### Phase 2 验收标准

- session 结束后 30 秒内生成 session_summary
- skill_patterns 正确识别跨 pane_id 的重复工具序列
- 向量相似度检索返回相关历史 session
- Skill 生命周期转换有日志记录，转换可逆

---

## Phase 3 — Insight Engine

**目标**：事件驱动的分析，在不打断工作流的前提下，在 Web UI 中展示带证据链的主动建议。

---

## 4. 触发事件

| 触发时机 | 触发条件 | 创建的 Insight 类型 |
|----------|---------|-------------------|
| session_end | pattern_hash 出现次数 >= 5 | new_skill 建议 |
| session_end | 已知 Skill 的 correction_count > 2 | improve_skill 建议 |
| tool_event | 当前工具序列与历史 session 相似度 > 0.88 | 上下文注入提示 |
| intervention | 相同纠正文本跨 session 出现 3+ 次 | 自动化候选建议 |
| attention_log | 4+ 个 pane 同时需要处理 | 认知负载警告 |
| skill_usage | skill.outcome 连续 2 次为 failed | Skill 审查提醒 |

### 触发器实现模式

```python
# insight_engine/triggers.py

class InsightTrigger:
    """所有触发器的基类，注册为 SessionTracker 的事件监听器"""

    async def on_session_end(self, pane_id: str, db) -> None:
        """session 结束时调用"""

    async def on_tool_event(self, event: ParsedEvent, db) -> None:
        """每次工具调用时调用"""

    async def on_intervention(self, intervention: dict, db) -> None:
        """每次开发者干预时调用"""


class NewSkillTrigger(InsightTrigger):
    async def on_session_end(self, pane_id: str, db) -> None:
        pattern = await db.get_pattern_for_session(pane_id)
        if pattern and pattern.occurrence_count >= cfg["insight_engine"]["min_occurrences"]:
            await self._create_insight(pattern, db)
```

---

## 5. Insight 数据格式

每条 Insight 必须携带 evidence 块，无证据不创建：

```json
{
  "type": "new_skill",
  "title": "建议将「Python 项目初始化」做成 Skill",
  "body": "## 检测到重复模式\n\n过去 2 周内出现了 7 次相似的工具调用序列...",
  "evidence": {
    "sessions": ["%21", "%34", "%67"],
    "occurrence_count": 7,
    "avg_duration_ms": 272000,
    "common_corrections": ["添加 .gitignore", "设置 Python 3.12"],
    "first_seen": 1714000000000
  }
}
```

`body` 字段为 Markdown，由 Anthropic API 生成，前端渲染展示。

---

## 6. UI：Insight Panel

右侧可折叠抽屉，Badge 显示未读数量。

### 交互规范

- 每条 Insight 包含：标题、Markdown 正文（渲染）、证据摘要、操作按钮
- 操作按钮：`[接受 → 生成草稿]` `[Snooze 1小时]` `[Snooze 1天]` `[忽略]`
- 接受后弹出模态框展示生成的 Skill 草稿（可编辑）
- `[全部 Snooze]` 按钮，适合专注工作时使用
- **Insight 永远不主动弹出**，只通过 Badge 数字提示；Panel 由用户主动打开

### Snooze 实现

```python
@router.patch("/api/insights/{insight_id}")
async def update_insight(insight_id: int, body: InsightUpdate):
    if body.action == "snooze":
        duration = {"1h": 3600, "1d": 86400}.get(body.duration, 3600)
        snoozed_until = now_ms() + duration * 1000
        await db.update_insight(insight_id, status="snoozed",
                                snoozed_until=snoozed_until)
    elif body.action == "accept":
        await db.update_insight(insight_id, status="accepted")
        # 触发 Skill 草稿生成
        asyncio.create_task(generate_skill_draft(insight_id))
```

---

## 7. 跨 Session 上下文注入

当运行中的 agent session 与历史 session 相似度 > 0.88 时：

```python
# insight_engine/triggers.py

class ContextInjectionTrigger(InsightTrigger):
    async def on_tool_event(self, event: ParsedEvent, db) -> None:
        current_summary = await build_partial_summary(event.pane_id, db)
        similar = await find_similar_sessions(current_summary, top_k=3, db=db)

        for past_pane_id in similar:
            similarity = await compute_similarity(current_summary, past_pane_id, db)
            if similarity > cfg["insight_engine"]["similarity_threshold"]:
                # 通过 WebSocket 推送非阻塞 toast 通知
                await broadcaster.broadcast({
                    "type": "context_suggestion",
                    "pane_id": event.pane_id,
                    "similar_session": past_pane_id,
                    "similarity": similarity,
                    "message": f"与 {days_ago(past_pane_id)} 天前的 session 高度相似，有可用上下文"
                })
                break   # 每次最多推送一条，避免干扰
```

前端展示为非阻塞 Toast，用户可点击查看历史 session 的 key_decisions，并一键将上下文发送给当前 agent。

### Phase 3 验收标准

- 48 小时正常使用中，Insight 无误报（evidence 阈值未达到不创建）
- Insight Panel Badge 在打开 Panel 后清零
- Snooze 在配置时长内正确屏蔽同类 Insight
- 相似度匹配 Toast 在检测到匹配后 10 秒内推送
- 生成的 Skill 草稿为有效 Markdown，可直接用作 Claude skill 文件
