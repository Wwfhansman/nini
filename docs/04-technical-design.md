# 技术设计

## 技术栈

后端：

- Python。
- FastAPI。
- Pydantic。
- SQLite。
- httpx / requests。
- websockets 可用于 ASR provider 内部接入。

前端：

- React + Vite。
- CSS Modules 或普通 CSS。
- 临时测试页可以用简单 HTML/React 单页。

AI 服务：

- 七牛 MaaS OpenAI-compatible API。
- 火山方舟流式 ASR。
- 豆包语音合成大模型 1.0。

## 核心对象

### TerminalState

代表厨房终端当前状态。

字段：

- `terminal_id`
- `ui_mode`
- `dish_name`
- `recipe`
- `current_step_index`
- `timer_status`
- `timer_remaining_seconds`
- `active_adjustments`
- `last_speech`
- `updated_at`

### RecipePlan

代表当前菜谱计划。

字段：

- `dish_name`
- `servings`
- `estimated_minutes`
- `reasoning_summary`
- `ingredients`
- `steps`
- `adjustments`

### CookingStep

字段：

- `index`
- `title`
- `instruction`
- `ingredients`
- `heat`
- `duration_seconds`
- `tips`
- `changed_by_memory`
- `changed_by_vision`

### AgentOutput

模型必须输出的结构。

字段：

- `intent`
- `ui_mode`
- `speech`
- `ui_patch`
- `tool_calls`
- `memory_writes`
- `inventory_patches`
- `recipe_adjustments`

## Agent 执行流程

```text
handle_chat(input)
  1. load terminal_state
  2. router checks P0
  3. if P0 -> apply local control
  4. retrieve memories
  5. summarize inventory
  6. build prompt
  7. call model provider
  8. parse and validate AgentOutput
  9. execute memory/inventory/recipe skills
  10. update terminal_state
  11. record tool_events
  12. return state snapshot
```

## Schema 校验

必须使用 Pydantic。

如果模型输出失败：

1. 尝试从文本中提取 JSON。
2. 使用默认字段补齐。
3. 如果仍失败，返回 fallback response。
4. 记录 `tool_event`，标记 `agent_parse_failed`。

## Skill 执行

模型输出 `tool_calls` 只是意图，后端决定实际执行。

不允许：

- 模型指定任意函数名。
- 模型传 SQL。
- 模型决定文件路径。

允许的 tool 白名单：

- `memory_write`
- `memory_search`
- `inventory_update`
- `inventory_search`
- `recipe_plan`
- `recipe_adjust`
- `recipe_knowledge_search`
- `vision_observe`

## Recipe 设计

首版采用 recipe catalog + rules。

固定主菜：

- 低脂不辣番茄鸡胸肉滑蛋。

可扩展菜品：

- 番茄炒蛋。
- 鸡胸肉沙拉。
- 鸡蛋豆腐羹。
- 番茄豆腐汤。
- 鸡胸肉滑蛋盖饭。

调整规则：

```text
if user dislikes sour:
  reduce tomato amount
  increase egg ratio
  remove vinegar
  shorten tomato frying time

if mother dislikes spicy:
  remove chili and spicy seasoning

if user is losing fat:
  reduce oil
  avoid sugar
  prefer chicken breast / egg / tofu

if tomato is half:
  adjust serving to 1
  reduce tomato-heavy steps
```

## Vision 设计

Vision provider 输出统一结构：

```json
{
  "scene": "kitchen_counter",
  "ingredients": [
    {"name": "番茄", "amount": "半个", "confidence": 0.91}
  ],
  "notes": ["番茄数量不足原计划"]
}
```

Vision 不直接改 UI，而是：

```text
vision_observation
  -> inventory_update
  -> recipe_adjust
  -> terminal_state update
```

## Speech 设计

语音不是核心智能层，只是入口和播报层。

ASR：

- 浏览器录音。
- 后端转发火山 ASR。
- 获取 final transcript。
- transcript 调 `/api/chat`。

TTS：

- Agent output 中的 `speech` 传给火山 TTS。
- 返回音频给前端播放。
- `speech` 必须短，复杂内容在屏幕显示。

软停止：

- 用户开始新一轮录音时，前端停止当前音频播放。
- 不做复杂声学打断。

## 临时测试优先

正式前端前，必须先完成测试页面：

- 输入 terminal_id。
- 输入文本。
- 发送 chat。
- 上传图片。
- 点击 control。
- 查看 JSON state。
- 查看 DB 变化。

这样后端闭环先稳定，再做正式终端 UI。
