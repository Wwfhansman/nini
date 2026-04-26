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
QINIU_BASE_URL=https://api.qnaigc.com/v1
QINIU_API_KEY=
MODEL_FAST_CHAT=
MODEL_VISION=
MODEL_AGENT=
MODEL_AGENT_THINKING=
```

Provider 接口建议：

```python
class ModelProvider:
    def chat_json(self, messages, model, timeout): ...
    def vision(self, image_bytes, prompt, model, timeout): ...
```

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

### hybrid

- Agent 使用真实 LLM。
- vision 或 speech 使用 mock。

### real

- 全部调用真实 provider。

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
