# 模型与第三方 API 接入

## 模型分工

```text
P0 本地状态机
  - 开始、下一步、暂停、继续、完成
  - 不调用模型

P1 Doubao-Seed 1.6 Flash
  - 快速短对话
  - 视觉识别
  - 简单改写

P2 DeepSeek-V4-Flash non-thinking
  - 常规 Agent 决策
  - 工具调用规划
  - 结构化 JSON 输出

P3 DeepSeek-V4-Flash thinking
  - 复杂规划
  - 复盘
  - 多约束决策

Speech
  - 火山方舟 ASR
  - 豆包 TTS 1.0
```

## 七牛 MaaS

用途：

- 对话模型。
- 视觉模型。
- Agent 任务模型。

接入原则：

- provider 层封装。
- 模型 ID 由配置控制。
- 不在业务代码写死模型名称。
- 支持 OpenAI-compatible chat completions。

环境变量：

```env
DEMO_MODE=mock
QINIU_BASE_URL=https://api.qnaigc.com/v1
QINIU_API_KEY=
MODEL_FAST_CHAT=
MODEL_VISION=
MODEL_AGENT=
MODEL_AGENT_THINKING=
PROVIDER_TIMEOUT_SECONDS=30
ENABLE_PROVIDER_LOGS=true
```

Provider 接口建议：

```python
class ModelProvider:
    def chat_json(self, messages, model, timeout): ...
    def vision(self, image_bytes, prompt, model, timeout): ...
```

当前实现：

- `backend/agent/providers.py` 提供 `MockAgentProvider`、`QiniuChatProvider`、`MockVisionProvider`、`QiniuVisionProvider`。
- 七牛 chat 和 vision 都使用 OpenAI-compatible `/chat/completions`。
- 请求头使用 `Authorization: Bearer ${QINIU_API_KEY}`，不向前端暴露 key。
- chat 优先发送 `response_format={"type":"json_object"}`；如果模型返回 400/422，则自动重试无 `response_format` 的 JSON prompt 约束。
- 真实 provider 返回会经过 `AgentOutput` 或 `VisionObservation` Pydantic 校验。
- JSON 解析失败、缺 key、HTTP 失败都会记录 provider 事件和 provider log，并 fallback 到 mock，避免破坏 `terminal_state`。
- provider logs 只记录 provider、model、status、latency、error 摘要，不记录 API key，也不记录图片 base64。

## 火山 ASR

用户提供文档：

- https://www.volcengine.com/docs/6561/1354869?lang=zh

用途：

- 流式语音识别大模型。
- 免费额度 20 小时。

接入建议：

- 后端连接火山 WebSocket。
- 前端音频不直接发火山，避免暴露密钥。
- 音频优先使用 16kHz、mono、pcm_s16le。
- 分包建议 100-200ms，demo 可用 200ms。

首版可以先做两层：

1. 非流式录音上传，快速验证闭环。
2. 再升级为后端流式转发。

配置：

```env
VOLC_ASR_APP_KEY=
VOLC_ASR_ACCESS_KEY=
VOLC_ASR_RESOURCE_ID=
```

## 豆包 TTS 1.0

用户提供文档：

- https://www.volcengine.com/docs/6561/1719100?lang=zh

音色：

```text
zh_female_wanwanxiaohe_moon_bigtts
```

免费额度：

```text
40000 字
```

使用原则：

- 只播报短句。
- 长信息显示在屏幕上。
- TTS 失败不影响主流程。

配置：

```env
VOLC_TTS_APP_ID=
VOLC_TTS_ACCESS_TOKEN=
VOLC_TTS_CLUSTER=
VOLC_TTS_VOICE_TYPE=zh_female_wanwanxiaohe_moon_bigtts
```

## DEMO_MODE

### mock

- LLM 返回固定 JSON。
- vision 返回固定 observation。
- ASR/TTS 可不启用。
- 不需要任何 API key，mock demo runner 必须始终通过。

### hybrid

- Agent 使用真实 LLM。
- vision 默认可继续使用 mock；如果配置了 `MODEL_VISION` 和 key，则可调用真实视觉 provider。
- 真实 provider 失败时 fallback 到 mock。

### real

- 全部调用真实 provider。
- 缺少 key 或模型配置时不会崩溃，会记录 provider fallback 事件。

## 验证命令

启动后端：

```bash
./.venv/bin/uvicorn backend.app:app --reload
```

mock demo：

```bash
./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

hybrid smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode hybrid-smoke --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

无 `QINIU_API_KEY` 或 `MODEL_AGENT` 时，hybrid smoke 会输出 `SKIPPED` 并返回成功；配置后会额外调用一次 `/api/chat`，并要求真实 `provider_call` 成功。若本次 chat fallback 到 mock，脚本会返回失败。

## Provider 失败处理

LLM 失败：

- 尝试 mock fallback。
- 记录 provider_logs。
- 返回不破坏状态的提示。

Vision 失败：

- 使用 mock vision。
- 标记事件：`vision_provider_fallback`。

TTS 失败：

- 前端显示文本。
- 不阻塞流程。

ASR 失败：

- 允许文本输入。

## 模型调用不要串行过多

避免：

```text
Doubao -> DeepSeek -> Doubao -> TTS
```

推荐：

```text
简单任务 -> Doubao or template
复杂任务 -> DeepSeek outputs speech + ui_patch
视觉任务 -> Doubao vision -> DeepSeek/recipe adjusts when needed
```

## 官方文档引用

- 七牛云 AI 推理 API：`https://developer.qiniu.com/aitokenapi/12882/ai-inference-api`
- 火山方舟流式语音识别：`https://www.volcengine.com/docs/6561/1354869?lang=zh`
- 豆包语音合成大模型：`https://www.volcengine.com/docs/6561/1719100?lang=zh`
- DeepSeek Tool Calls：`https://api-docs.deepseek.com/guides/function_calling`
