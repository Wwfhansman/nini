# 临时测试页面方案

## 为什么需要临时测试页

正式前端最后做。前期必须先用临时测试页把后端闭环调通，避免同时调 UI 和业务逻辑。

临时测试页不是省赛正式界面，但必须能完成：

- chat 输入。
- vision 上传。
- TTS 文本转语音。
- ASR 上传音频识别。
- control 操作。
- state 查看。
- tool_events 查看。
- memory/inventory 查看。

## 路径建议

```text
frontend-test/
  index.html
```

或由 FastAPI 静态挂载：

```text
/test-console
```

当前实现采用 FastAPI 静态页面：

```text
backend/static/test-console.html
```

启动后端后访问：

```bash
./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

```text
http://127.0.0.1:8000/test-console
```

临时测试页不是正式前端，不承担最终视觉设计和交互体验，只用于后端闭环调试、演示录制和 API 可观测性检查。

## 页面结构

```text
左侧：操作区
  - terminal_id
  - 文本输入
  - 发送 chat
  - 上传图片
  - TTS 文本框和播放控件
  - ASR 音频上传和发送到 chat
  - control buttons

中间：state JSON
  - terminal_state
  - current recipe
  - current step

右侧：调试信息
  - memories
  - inventory
  - tool_events
  - provider_logs
  - raw response
```

页面顶部显示当前 `DEMO_MODE` 和 provider 配置状态。测试页只显示是否已配置，不显示 `QINIU_API_KEY`。

## 必须支持的操作

### 发送 chat

默认填充：

```text
我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？
```

### 上传 vision

选择图片，调用 `/api/vision`。

### 语音调试

- TTS 文本默认 `进入下一步。`，调用 `/api/speech/tts`。
- 如果返回 `audio_base64`，页面直接播放；如果 mock 成功但无音频，则显示成功状态。
- ASR 上传音频文件，调用 `/api/speech/asr`。
- ASR 返回文本后，可一键发送到 `/api/chat`。
- 页面只显示语音 provider 状态，不暴露火山密钥。

### 控制按钮

- start。
- next_step。
- pause。
- resume。
- finish。
- reset。

### 导出记忆

调用 `/api/export/memory` 并显示 Markdown。

### 一键演示流程

测试页提供“一键演示流程”按钮，按顺序调用：

1. `reset`
2. `/api/chat` 初始规划
3. `/api/vision` mock 视觉修正
4. `start`
5. `/api/chat` 写入“不喜欢太酸”
6. `next_step`
7. `pause`
8. `resume`
9. `finish`
10. `/api/export/memory`

如果没有选择图片，页面会上传一个空的 mock 文件；后端当前使用 mock vision，不解析真实图片内容。

## Demo runner

除页面外，还提供命令行验证脚本：

```bash
./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

脚本会输出每一步的 HTTP 状态、`state.ui_mode`、最新事件和关键断言结果，用于快速确认 mock demo 主线仍可复现。

hybrid smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode hybrid-smoke --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

hybrid smoke 会先检查 `/health` 和 `/api/state`。如果后端未配置七牛 key 或 `MODEL_AGENT`，真实 chat 调用会被跳过，不影响 mock demo 验证；如果已配置，则必须出现真实 `provider_call` 成功，fallback 到 mock 会被判定为失败。

speech smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode speech-smoke --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

speech smoke 会验证 `/api/speech/tts` 和 `/api/speech/asr`。mock 模式不需要 key；配置真实 TTS 后，如果 TTS fallback 到 mock 会判定失败。ASR 本轮仍允许 mock fallback。

## 调试成功标准

正式前端开工前，临时测试页必须能走完：

1. chat 规划菜品。
2. vision 修正菜谱。
3. start cooking。
4. 记住“不喜欢太酸”并改步骤。
5. next/pause/resume。
6. finish review。
7. export memory。

## 与正式前端关系

临时测试页用于验证后端，不追求美观。

正式前端只在临时测试页通过后开始。正式前端不应重新实现业务逻辑，只消费同一批 API。
