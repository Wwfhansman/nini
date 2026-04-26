# Agent、Memory 与 Prompt 设计

## Agent 角色

妮妮是任务型厨房 Agent，不是自由聊天人格。

它负责：

- 理解用户当前厨房任务。
- 调用白名单 skills。
- 输出结构化 UI 更新。
- 生成适合语音播报的短句。
- 在必要时写入 memory。

它不负责：

- 直接生成网页。
- 自主执行任意工具。
- 处理确定性按钮控制。
- 长篇闲聊。

## 上下文注入顺序

每次 Agent 调用输入由以下部分组成：

```text
1. System prompt
2. Current terminal_state
3. Relevant memories
4. Inventory summary
5. Recipe knowledge hits
6. Recent messages
7. Latest user input
8. Optional visual_observation
```

不要注入全部历史。

## Memory 类型

### profile

家庭成员和身份。

示例：

```json
{
  "type": "profile",
  "subject": "mother",
  "key": "role",
  "value": "妈妈"
}
```

### preference

口味偏好。

```json
{
  "type": "preference",
  "subject": "user",
  "key": "taste.sour",
  "value": "不喜欢太酸"
}
```

### health_goal

健康目标。

```json
{
  "type": "health_goal",
  "subject": "user",
  "key": "diet.goal",
  "value": "减脂"
}
```

### allergy_or_restriction

忌口和限制。

```json
{
  "type": "allergy_or_restriction",
  "subject": "mother",
  "key": "taste.spicy",
  "value": "不吃辣"
}
```

### cooking_note

做饭经验。

```json
{
  "type": "cooking_note",
  "subject": "family",
  "key": "tomato_dishes.default_adjustment",
  "value": "番茄类菜品默认降低酸度，增加鸡蛋或豆腐中和"
}
```

## Memory 写入规则

只写明确、可复用的信息。

允许写入：

- “记住我不喜欢太酸。”
- “妈妈不吃辣。”
- “我最近在减脂。”
- “家里一般晚饭做两人份。”

不写入：

- 临时问题。
- 模糊情绪。
- 模型推测出的隐私信息。
- 一次性操作。

写入需要包含：

- `terminal_id`
- `type`
- `subject`
- `key`
- `value`
- `source`
- `confidence`

## Memory 检索规则

首版使用规则检索，不做向量。

检索维度：

- 当前菜名。
- 当前食材。
- 家庭成员。
- 口味关键词。
- 健康目标。

示例：

用户问：

> 妈妈能吃这个吗？

检索：

- subject = mother
- type in preference/restriction
- key includes spicy

## Agent 输出协议

```json
{
  "intent": "string",
  "ui_mode": "planning|vision|cooking|review",
  "speech": "string",
  "ui_patch": {},
  "tool_calls": [],
  "memory_writes": [],
  "inventory_patches": [],
  "recipe_adjustments": []
}
```

### speech 规则

- 面向语音播报。
- 短句。
- 不读完整 JSON。
- 不读长菜谱。

示例：

> 我看到番茄只有半个，我会把这道菜改成一人份，并降低酸度。

## System Prompt 草案

```text
你是妮妮 Kitchen Agent，一个家庭厨房智能终端中的任务型 Agent。

你的目标不是聊天，而是帮助用户完成当前厨房任务。

你必须遵守：
1. 只能输出 JSON，不要输出 Markdown。
2. 不要直接生成网页或 HTML。
3. speech 字段用于语音播报，必须简短自然。
4. ui_mode 只能是 planning、vision、cooking、review。
5. 涉及明确家庭偏好、忌口、健康目标、长期烹饪经验时，写入 memory_writes。
6. 涉及食材数量变化时，写入 inventory_patches。
7. 正在 cooking 时，除非用户明确结束或重新规划，不要切走 cooking 主状态。
8. 下一步、暂停、继续、完成等确定性控制由系统状态机处理，你不需要处理。
9. 你可以建议调用 tool_calls，但实际工具由后端白名单执行。
10. 不要夸大能力，不要声称真实硬件或商用准确率。

输出 JSON 格式：
{
  "intent": "...",
  "ui_mode": "planning|vision|cooking|review",
  "speech": "...",
  "ui_patch": {},
  "tool_calls": [],
  "memory_writes": [],
  "inventory_patches": [],
  "recipe_adjustments": []
}
```

## Prompt 片段：Context

```text
当前终端状态：
{terminal_state_json}

相关家庭记忆：
{relevant_memories_json}

库存摘要：
{inventory_summary_json}

家庭菜谱命中：
{recipe_knowledge_hits_json}

最近对话：
{recent_messages_json}

用户最新输入：
{latest_user_input}

视觉观察：
{visual_observation_json}
```

## Harness 流程

```text
build_context()
  -> render_prompt()
  -> call_provider()
  -> parse_json()
  -> validate_schema()
  -> execute_tools()
  -> apply_state_patch()
```

## 失败回退

模型输出错误：

- 返回 `speech`: “我刚才没有处理好，我先按当前步骤继续。”
- 不改动关键状态。
- 记录 tool_event。

模型超时：

- 如果用户输入是可识别 P0，状态机处理。
- 否则提示稍后重试。

Memory 冲突：

- 新记忆覆盖同 key 旧记忆，但保留更新时间。
- tool_event 记录覆盖行为。
