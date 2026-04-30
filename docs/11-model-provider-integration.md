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
  - 豆包 TTS 1.0 / 小米 MiMo TTS
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

主语音入口：

- 前端连接后端 `/ws/voice`，不直接连接火山，避免暴露密钥。
- 前端采集 PCM16 16kHz mono 音频，按 100-200ms 分包发送 binary chunk。
- 前端本地 VAD 检测到一次说话后的短暂停顿时，发送 `{"type":"audio.end"}`，
  后端结束当前 ASR utterance 并触发 final 文本处理。
- 后端 voice session 连接火山 WebSocket，转发 partial/final transcript。
- ASR final 文本由后端进行“妮妮/腻妮/nini”软件唤醒和会话状态判断，再进入
  `runtime.handle_chat`。

文件上传兜底：

- `/api/speech/asr` 继续接受 multipart 音频上传，仅作为调试和浏览器不支持流式采集时的兜底。
- 主产品体验不再依赖“录完上传文件”。

配置：

```env
VOLC_ASR_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
VOLC_ASR_APP_KEY=
VOLC_ASR_ACCESS_KEY=
VOLC_ASR_RESOURCE_ID=volc.bigasr.sauc.duration
SPEECH_PROVIDER_MODE=mock
SPEECH_TIMEOUT_SECONDS=30
VOICE_WAKE_WORDS=妮妮,腻妮,nini
VOICE_ACTIVE_IDLE_SECONDS=25
VOICE_SLEEP_SECONDS=60
```

本地后端启动时会自动读取仓库根目录 `.env`，但不会覆盖已经在 shell 中 export 的变量。
修改 `.env` 后需要重启后端。调试真实 ASR 时，
`/health` 应显示 `providers.speech_provider_mode=auto|real` 且
`providers.volc_asr_configured=true`。

当前实现：

- `/ws/voice` 是主语音入口，协议事件包括 `session.state`、`asr.partial`、`asr.final`、
  `wake.detected`、`agent.event` 和 `agent.response`。
- 客户端除音频 binary chunk 外，还会发送 `session.start`、`audio.end`、`session.sleep`。
- `/api/speech/asr` 仍接受 multipart 音频上传。
- `SPEECH_PROVIDER_MODE=mock` 返回固定文本 `下一步`。
- `SPEECH_PROVIDER_MODE=auto|real` 优先进入 `VolcStreamingASRProvider`。缺少配置、连接失败或
  provider 异常时降级到 `MockStreamingASRProvider`，WebSocket 不崩溃。
- 火山流式 provider 使用推荐接口
  `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`，Header 为
  `X-Api-App-Key`、`X-Api-Access-Key`、`X-Api-Resource-Id`、`X-Api-Connect-Id`。
- 初始 request payload 使用 `audio.format=pcm`、`codec=raw`、`rate=16000`、`bits=16`、
  `channel=1`，并开启 `request.enable_punc` 与 `request.enable_itn`。
- provider 事件记录 `speech_asr`，不记录音频内容或 base64。
- API key 不写入前端、事件或错误响应；provider 错误只保留脱敏摘要。

隐私口径：

- 休眠态和未授权状态不采集、不上传音频。
- 待唤醒态只存在于用户显式开启 Web 语音会话之后，属于 demo 内软件唤醒，不是系统级离线唤醒。
- 会话态仅上传前端 VAD 判断后的有效语音片段或少量静音边界包；超时后回到待唤醒或休眠。

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
VOLC_TTS_ACCESS_KEY=
VOLC_TTS_ACCESS_TOKEN=
VOLC_TTS_RESOURCE_ID=seed-tts-1.0
VOLC_TTS_VOICE_TYPE=zh_female_wanwanxiaohe_moon_bigtts
SPEECH_PROVIDER_MODE=mock
SPEECH_TIMEOUT_SECONDS=30
```

当前实现：

- `/api/speech/tts` 输入 `terminal_id` 和 `text`。
- `text` 为空返回 400；长度限制为 300 字以内。
- mock TTS 返回 `provider=mock_tts` 且 `audio_base64=""`，API 不失败，测试台显示 mock 成功。
- `SPEECH_PROVIDER_MODE=auto|real` 优先调用火山豆包 TTS 1.0 V3 单向短文本接口 `/api/v3/tts/unidirectional`，返回 base64 MP3；失败时 fallback 到 mock。
- V3 鉴权使用 `X-Api-App-Id`、`X-Api-Access-Key`、`X-Api-Resource-Id`，不再使用旧 V1 `/api/v1/tts`。
- `VOLC_TTS_RESOURCE_ID` 默认 `seed-tts-1.0`，如果控制台给出 `volc.service_type.10029` 等资源 ID，应按实际值覆盖。
- `VOLC_TTS_ACCESS_TOKEN` 作为旧字段名兼容保留，推荐使用 `VOLC_TTS_ACCESS_KEY`。
- provider 事件记录 `speech_tts`，只记录音频是否存在，不记录音频 base64。

## Optional Xiaomi MiMo TTS

小米 MiMo 只用于语音播报 TTS，不接入 ASR。ASR 主链路仍然是前端 `/ws/voice`
流式会话加后端火山流式识别或 mock fallback。

配置：

```env
SPEECH_TTS_VENDOR=bytedance
MIMO_API_KEY=
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_TTS_MODEL=mimo-v2.5-tts
MIMO_TTS_VOICE=茉莉
MIMO_TTS_STYLE=温柔、清晰、像厨房里的智能助手，语速自然，提醒简洁。
```

当前实现：

- `/api/speech/tts` 支持可选 `tts_vendor=bytedance|xiaomi|mock`，用于单次播报服务切换，不修改 `.env`。
- 前端正式终端提供“语音播报：字节 / 小米”切换，自动播报和手动重播都会使用当前选择。
- MiMo 请求使用 `POST {MIMO_BASE_URL}/chat/completions`，模型默认 `mimo-v2.5-tts`。
- 合成文本放在 assistant message，风格提示放在 user message，音频格式为 wav。
- MiMo 失败或未配置 `MIMO_API_KEY` 时 fallback 到 mock TTS；API key 不进入前端、事件或错误响应。

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
./.venv/bin/pip install -r backend/requirements.txt
./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

注意：必须使用项目 `.venv` 里的 uvicorn。使用系统 Python 启动的旧进程可能没有
`websockets` 依赖，也可能没有加载 `/ws/voice` 路由，浏览器会表现为
`WebSocket connection ... /ws/voice failed`。
如果本机 shell 配置了 SOCKS 代理，火山 WebSocket 连接还需要
`python-socks[asyncio]`；该依赖已写入 `backend/requirements.txt`，更新后重新执行
`./.venv/bin/pip install -r backend/requirements.txt`。

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
- `speech_tts` event 标记 fallback。

ASR 失败：

- 允许文本输入。
- `speech_asr` event 标记 fallback。

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
