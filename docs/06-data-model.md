# 数据模型

数据库：SQLite。

首版不做复杂迁移系统，可以先使用 `database.init_db()` 创建表。后续可迁移到 Alembic。

## 通用字段

多数表包含：

- `id`
- `terminal_id`
- `created_at`
- `updated_at`

时间建议使用 ISO string 或 Unix timestamp，项目内保持一致。

## terminals

终端表。

```sql
CREATE TABLE terminals (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

## memories

结构化长期记忆。

```sql
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  type TEXT NOT NULL,
  subject TEXT NOT NULL,
  key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  confidence REAL DEFAULT 1.0,
  source TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

建议索引：

```sql
CREATE INDEX idx_memories_terminal ON memories(terminal_id);
CREATE INDEX idx_memories_lookup ON memories(terminal_id, type, subject, key);
```

示例：

```json
{
  "id": "mem_001",
  "terminal_id": "demo-kitchen-001",
  "type": "preference",
  "subject": "user",
  "key": "taste.sour",
  "value_json": {"text": "不喜欢太酸"},
  "confidence": 0.95,
  "source": "user_explicit"
}
```

## inventory_items

库存。

```sql
CREATE TABLE inventory_items (
  id TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  amount TEXT,
  unit TEXT,
  category TEXT,
  freshness TEXT,
  source TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

示例：

```json
{
  "name": "番茄",
  "amount": "半个",
  "category": "蔬菜",
  "source": "vision"
}
```

## terminal_state

当前终端状态。

```sql
CREATE TABLE terminal_state (
  terminal_id TEXT PRIMARY KEY,
  ui_mode TEXT NOT NULL,
  state_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`state_json` 示例：

```json
{
  "ui_mode": "cooking",
  "dish_name": "低脂不辣番茄鸡胸肉滑蛋",
  "current_step_index": 1,
  "timer_status": "running",
  "timer_remaining_seconds": 180,
  "recipe": {
    "servings": "1人份",
    "steps": []
  },
  "active_adjustments": [
    "降低酸度",
    "增加鸡蛋比例"
  ]
}
```

## tool_events

工具调用和状态变化时间线。

```sql
CREATE TABLE tool_events (
  id TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  name TEXT NOT NULL,
  input_json TEXT,
  output_json TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

示例：

```json
{
  "event_type": "local_control",
  "name": "next_step",
  "status": "success",
  "output_json": {"model_called": false}
}
```

## conversations

简化对话历史。

```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);
```

只取最近 4-6 条注入模型。

## recipe_documents

家庭菜谱知识库。

```sql
CREATE TABLE recipe_documents (
  id TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  content TEXT NOT NULL,
  parsed_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

首版检索：

- title like。
- content like。
- tags in parsed_json。

后续可以加 SQLite FTS 或向量库。

## provider_logs

可选。记录外部 provider 请求摘要，便于排查。

```sql
CREATE TABLE provider_logs (
  id TEXT PRIMARY KEY,
  terminal_id TEXT,
  provider TEXT NOT NULL,
  model TEXT,
  status TEXT NOT NULL,
  latency_ms INTEGER,
  error TEXT,
  created_at TEXT NOT NULL
);
```

不要存 API key。

## 数据写入原则

- Memory 和 inventory 必须真实落库。
- terminal_state 是后端唯一状态源。
- tool_events 用于答辩展示和调试。
- conversations 只用于上下文，不是长期记忆。
- recipe_documents 是家庭菜谱知识库，不替代 memory。
