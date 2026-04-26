# API 规范

基础路径：

```text
/api
```

所有请求建议包含 `terminal_id`。省赛 demo 默认：

```text
demo-kitchen-001
```

## POST /api/chat

用户文本输入，可能进入 Agent，也可能被 router 判定为 P0 指令。

### Request

```json
{
  "terminal_id": "demo-kitchen-001",
  "text": "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？",
  "source": "text"
}
```

### Response

```json
{
  "ok": true,
  "data": {
    "speech": "我建议做低脂不辣番茄鸡胸肉滑蛋。",
    "intent": "plan_recipe"
  },
  "state": {
    "ui_mode": "planning",
    "dish_name": "低脂不辣番茄鸡胸肉滑蛋"
  },
  "events": [
    {"name": "memory_write", "status": "success"},
    {"name": "inventory_update", "status": "success"},
    {"name": "recipe_plan", "status": "success"}
  ],
  "error": null
}
```

## POST /api/vision

上传图片并触发视觉识别、库存修正和菜谱调整。

### Request

`multipart/form-data`

字段：

- `terminal_id`
- `purpose`: `ingredients|pan_state|plating`
- `image`

### Response

```json
{
  "ok": true,
  "data": {
    "observation": {
      "ingredients": [
        {"name": "番茄", "amount": "半个", "confidence": 0.91},
        {"name": "鸡胸肉", "amount": "少量", "confidence": 0.86},
        {"name": "鸡蛋", "amount": "2个", "confidence": 0.94}
      ]
    },
    "speech": "我看到番茄只有半个，我会把这道菜改成一人份。"
  },
  "state": {
    "ui_mode": "vision"
  },
  "events": [
    {"name": "vision_observe", "status": "success"},
    {"name": "inventory_update", "status": "success"},
    {"name": "recipe_adjust", "status": "success"}
  ],
  "error": null
}
```

## POST /api/control

本地状态机控制。

### Request

```json
{
  "terminal_id": "demo-kitchen-001",
  "command": "next_step"
}
```

合法 command：

- `start`
- `next_step`
- `previous_step`
- `pause`
- `resume`
- `finish`
- `reset`

### Response

```json
{
  "ok": true,
  "data": {
    "model_called": false,
    "speech": "进入下一步。"
  },
  "state": {
    "ui_mode": "cooking",
    "current_step_index": 2
  },
  "events": [
    {
      "event_type": "local_control",
      "name": "next_step",
      "status": "success",
      "output": {"model_called": false}
    }
  ],
  "error": null
}
```

## GET /api/state

获取当前终端状态。

### Query

```text
terminal_id=demo-kitchen-001
```

### Response

```json
{
  "ok": true,
  "data": {
    "terminal_id": "demo-kitchen-001",
    "state": {},
    "memories": [],
    "inventory": [],
    "tool_events": []
  },
  "state": {},
  "events": [],
  "error": null
}
```

## GET /api/export/memory

导出家庭记忆卡片。

### Query

```text
terminal_id=demo-kitchen-001
```

### Response

Content-Type:

```text
text/markdown
```

示例：

```md
# 张家厨房记忆卡

- 用户最近在减脂
- 用户不喜欢太酸
- 妈妈不吃辣
```

## POST /api/knowledge/recipe

导入家庭菜谱知识。

### Request

```json
{
  "terminal_id": "demo-kitchen-001",
  "title": "妈妈版番茄炒蛋",
  "content": "不放辣，鸡蛋多一点，出锅前加一点糖。"
}
```

### Response

```json
{
  "ok": true,
  "data": {
    "document_id": "recipe_doc_001"
  },
  "state": {},
  "events": [
    {"name": "recipe_knowledge_import", "status": "success"}
  ],
  "error": null
}
```

## POST /api/speech/asr

首版可做非流式上传录音文件，内部调用火山 ASR。

### Request

`multipart/form-data`

- `terminal_id`
- `audio`

### Response

```json
{
  "ok": true,
  "data": {
    "text": "下一步",
    "provider": "mock_asr",
    "fallback_used": false,
    "error": null
  },
  "state": {},
  "events": [
    {"name": "speech_asr", "status": "success"}
  ],
  "error": null
}
```

## POST /api/speech/tts

把 `speech` 转成音频。

### Request

```json
{
  "terminal_id": "demo-kitchen-001",
  "text": "进入下一步。"
}
```

### Response

可以返回：

- audio bytes。
- 或 base64。
- 或临时音频 URL。

省赛实现以最容易前端播放为准。

当前实现返回 base64：

```json
{
  "ok": true,
  "data": {
    "audio_base64": "",
    "mime_type": "audio/mpeg",
    "provider": "mock_tts",
    "voice_type": "mock",
    "fallback_used": false,
    "error": null
  },
  "state": {},
  "events": [
    {"name": "speech_tts", "status": "success"}
  ],
  "error": null
}
```

`text` 为空或超过 300 字返回 400，结构仍为 `ApiResponse`。
