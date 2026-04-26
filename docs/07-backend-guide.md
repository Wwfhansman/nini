# 后端开发文档

## 开发顺序

后端优先于正式前端。

推荐顺序：

1. `config.py`
2. `database.py`
3. Pydantic schemas
4. terminal state manager
5. local router/control
6. skills
7. mock providers
8. agent runtime
9. API layer
10. temporary test console
11. real providers

## 目录结构

```text
backend/
  app.py
  config.py
  database.py
  agent/
    runtime.py
    router.py
    schemas.py
    prompts.py
    providers.py
  skills/
    memory.py
    inventory.py
    recipe.py
    vision.py
    recipe_knowledge.py
  terminal/
    state.py
  speech/
    volc_asr.py
    volc_tts.py
    schemas.py
  mocks/
    agent_responses.py
    vision_responses.py
  tests/
```

## 配置

环境变量：

```env
APP_ENV=development
DEMO_MODE=mock
DB_PATH=./data/nini.db

QINIU_BASE_URL=https://api.qnaigc.com/v1
QINIU_API_KEY=
MODEL_FAST_CHAT=
MODEL_VISION=
MODEL_AGENT=

VOLC_ASR_APP_KEY=
VOLC_ASR_ACCESS_KEY=
VOLC_ASR_RESOURCE_ID=

VOLC_TTS_APP_ID=
VOLC_TTS_ACCESS_TOKEN=
VOLC_TTS_CLUSTER=
VOLC_TTS_VOICE_TYPE=zh_female_wanwanxiaohe_moon_bigtts
```

实际模型 ID 启动时最好通过 provider 探测或配置明确指定，不要散落在业务代码中。

## API 返回统一结构

```json
{
  "ok": true,
  "data": {},
  "state": {},
  "events": [],
  "error": null
}
```

错误：

```json
{
  "ok": false,
  "data": null,
  "state": {},
  "events": [],
  "error": {
    "code": "agent_parse_failed",
    "message": "模型输出解析失败，已回退"
  }
}
```

## 状态机

`terminal/state.py` 应提供：

- `get_state(terminal_id)`
- `reset_state(terminal_id)`
- `start_cooking(terminal_id)`
- `next_step(terminal_id)`
- `previous_step(terminal_id)`
- `pause_timer(terminal_id)`
- `resume_timer(terminal_id)`
- `finish_cooking(terminal_id)`
- `apply_ui_patch(terminal_id, patch)`

状态机必须记录 tool_event：

```json
{
  "event_type": "local_control",
  "name": "next_step",
  "output": {"model_called": false}
}
```

## Agent Runtime

输入：

```python
AgentRequest(
    terminal_id="demo-kitchen-001",
    text="记住我不喜欢太酸",
    visual_observation=None
)
```

输出：

```python
AgentResult(
    speech="好，我会把这道菜调得不那么酸。",
    state=...,
    events=[...]
)
```

## Skills 边界

### memory skill

职责：

- 写入 memory。
- 检索相关 memory。
- 导出 Markdown。

不负责：

- 判断是否应该写入。这个由 Agent output + runtime 决定。

### inventory skill

职责：

- upsert 食材。
- 按菜谱扣减库存。
- 生成 inventory summary。

### recipe skill

职责：

- 从 catalog 生成 recipe plan。
- 根据 memory/inventory/vision 调整 recipe。
- 生成 review 建议。

### vision skill

职责：

- 调用 vision provider 或 mock。
- 标准化 observation。

## Mock 策略

Mock 不是偷懒，是演示稳定性设计。

Mock 文件必须集中放在：

```text
backend/mocks/
```

不要把 mock 数据写死在 API 或前端。

## 测试建议

最低测试：

- P0 router 识别。
- state machine 下一步/暂停/完成。
- memory write/search。
- inventory update/deduct。
- Agent output schema 校验。
- mock demo script 端到端。

## 后端完成标准

后端在正式前端开始前必须满足：

- `/api/chat` 可完成规划、记忆写入、菜谱调整。
- `/api/vision` 可完成 mock vision、库存修正、菜谱调整。
- `/api/control` 可完成开始/下一步/暂停/继续/完成。
- `/api/state` 返回完整可渲染状态。
- tool_events 可展示完整时间线。
- 数据真实写入 SQLite。
