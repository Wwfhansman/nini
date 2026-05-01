# 妮妮 Kitchen Agent

面向家庭厨房场景的一顿饭任务型 AI 终端原型。

妮妮 Kitchen Agent 不是菜谱推荐器，也不是普通聊天助手。它通过语音/文本入口、厨房大屏工作台、视觉识别、家庭记忆、库存系统和本地状态机，帮助用户完成从家庭约束输入、菜品规划、食材现实修正、烹饪执行到复盘记录的一顿饭闭环。

## 当前建设目标

省赛版本优先完成一条稳定、可复现、可录制演示视频的闭环，同时保持源码结构可继续演进为真实产品原型。

核心演示：

1. 用户输入家庭约束和库存：用户减脂、妈妈不吃辣、家里有鸡胸肉/番茄/鸡蛋。
2. Agent 写入家庭记忆和库存，规划低脂不辣菜品。
3. 视觉识别发现实际食材不足，触发库存修正和菜谱调整。
4. 进入烹饪模式，状态机处理下一步、暂停、继续、完成。
5. 用户新增偏好“不喜欢太酸”，系统写入长期记忆并立即修改当前步骤。
6. 完成后生成复盘，扣减库存，导出家庭记忆卡片。

## 文档入口

- [项目总览](docs/00-project-brief.md)
- [需求文档 PRD](docs/01-prd.md)
- [演示脚本](docs/02-demo-script.md)
- [系统架构](docs/03-architecture.md)
- [技术设计](docs/04-technical-design.md)
- [Agent、Memory 与 Prompt 设计](docs/05-agent-memory-prompt.md)
- [数据模型](docs/06-data-model.md)
- [后端开发文档](docs/07-backend-guide.md)
- [API 规范](docs/08-api-spec.md)
- [前端开发文档](docs/09-frontend-guide.md)
- [临时测试页面方案](docs/10-test-console.md)
- [模型与第三方 API 接入](docs/11-model-provider-integration.md)
- [开发进程规划](docs/12-development-plan.md)
- [答辩与材料口径](docs/13-defense-materials.md)
- [实现检查清单](docs/14-implementation-checklist.md)

## 开发策略

采用后端先行：

1. 先实现数据库、状态机、技能模块、Agent JSON 协议。
2. 用临时测试页面调通后端功能和演示链路。
3. 后端闭环稳定后，再独立设计正式前端终端界面。
4. 最后联调语音、视觉、真实模型与演示模式。

正式演示终端在 `frontend/`，调试用临时页面在 `/test-console`，两者并存：
正式终端用于答辩与录制，`/test-console` 用于调试后端事件与一键 mock demo。

## 本地运行

安装后端依赖：

```bash
python3 -m venv .venv
./.venv/bin/pip install -r backend/requirements.txt
```

启动后端（必须用项目虚拟环境，不要用系统 Python 的 `python -m uvicorn`）：

```bash
./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

默认使用 `DEMO_MODE=mock`，不需要任何 API key，mock demo 始终应该可跑。
`/ws/voice` 流式语音会话依赖 `websockets`；如果本机设置了 SOCKS 代理，`websockets`
还需要 `python-socks[asyncio]`。这些依赖都已在 `backend/requirements.txt` 中声明。
如果浏览器报 `WebSocket connection ... /ws/voice failed`，先确认后端是用上面的
`.venv/bin/uvicorn` 命令启动，并且重启过后端。

启动后可以访问临时测试控制台：

```text
http://127.0.0.1:8000/test-console
```

临时测试控制台用于调通后端闭环和录制 mock 演示，不是正式前端。

运行可复现 mock demo：

```bash
DEMO_MODE=mock SPEECH_PROVIDER_MODE=mock ./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

运行 hybrid smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode hybrid-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

未配置七牛 MaaS key 或 `MODEL_AGENT` 时，hybrid smoke 会跳过真实 chat 调用并返回成功，避免影响本地/CI mock 验证。已配置时必须看到真实 `provider_call` 成功；如果 `/api/chat` fallback 到 mock，脚本会返回失败。真实模型首包可能超过 10 秒，赛前验收统一使用 `--timeout 60`。

运行 speech smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode speech-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

mock 语音不需要任何 key；配置真实 TTS 后，speech smoke 会要求 TTS 不 fallback。ASR 本轮仍是非流式上传接口和 mock fallback。

运行流式语音 real smoke：

```bash
./.venv/bin/python scripts/run_mock_demo.py --mode voice-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

`voice-smoke` 会连接 `/ws/voice`，发送一小段 PCM16 音频并确认后端启动 `volc_streaming_asr` 且未 fallback；它验证的是正式前端使用的实时语音路径，不要求测试音频识别出有效文本。

运行测试：

```bash
./.venv/bin/pytest backend/tests
```

## 正式前端

`frontend/` 是省赛演示用的厨房终端 UI（React + Vite，普通 CSS，零外部 CDN）。
后端默认监听 `http://127.0.0.1:8000`。开发环境下，HTTP API 走 Vite proxy，
语音 WebSocket 默认直连 `ws://127.0.0.1:8000/ws/voice`。

另开一个终端安装并启动前端：

```bash
cd frontend
npm install
npm run dev
# http://127.0.0.1:5173
```

构建生产包：

```bash
cd frontend
npm run build
npm run preview   # 可选，预览 dist/ 静态包
```

默认配置下，Vite 把 `/api`、`/ws`、`/health`、`/test-console`、`/static` 反代到
`http://127.0.0.1:8000`，浏览器看到的是同源，无需在后端开 CORS。
切换上游地址（例如 8000 端口被占）：

```bash
cd frontend
cp .env.example .env
# 修改 VITE_API_PROXY_TARGET=http://127.0.0.1:8001
# 可选：修改 VITE_WS_BASE_URL=ws://127.0.0.1:8001
```

如果要把构建产物部署到与后端不同源的地方，再用 `VITE_API_BASE_URL` 覆盖为绝对地址，
并自行解决 CORS。

正式前端与 `/test-console` 并存：
- `frontend/` 是面向答辩演示的终端 UI，含一键运行 demo、对话、视觉、烹饪、复盘。
- `/test-console` 仍然保留，用于直接观察 raw state / events / provider logs。

## 七牛 MaaS 配置

复制 `.env.example` 后按需设置环境变量，不提交 `.env`：

```env
DEMO_MODE=mock
QINIU_BASE_URL=https://api.qnaigc.com/v1
QINIU_API_KEY=
MODEL_AGENT=
MODEL_VISION=
PROVIDER_TIMEOUT_SECONDS=30
```

- `DEMO_MODE=mock`：全部使用 mock provider。
- `DEMO_MODE=hybrid`：chat 优先走七牛 MaaS，失败时 fallback 到 mock；vision 在配置模型后可走真实 provider，否则保持 mock。
- `DEMO_MODE=real`：chat 和 vision 优先走七牛 MaaS，失败时记录 provider 事件并 fallback，保证状态不被破坏。
- 模型 ID 以七牛控制台实际可用名称为准，业务代码不硬编码具体模型。

## 火山语音配置

语音主入口是 `/ws/voice` 流式会话：前端采集 PCM16 16k mono 音频发给后端，
后端再接火山流式 ASR 或 mock streaming fallback。`/api/speech/asr` 文件上传接口仍保留为调试兜底。
免费额度有限，`speech` 字段应保持短句。
后端本地启动时会自动读取仓库根目录 `.env`，不会覆盖 shell 里已经 export 的变量；修改 `.env`
后需要重启后端。

```env
SPEECH_PROVIDER_MODE=mock
SPEECH_TIMEOUT_SECONDS=30
VOLC_ASR_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
VOLC_ASR_RESOURCE_ID=volc.bigasr.sauc.duration
VOLC_ASR_APP_ID=
VOLC_ASR_ACCESS_TOKEN=
VOLC_ASR_APP_KEY=
VOLC_ASR_ACCESS_KEY=
VOLC_TTS_APP_ID=
VOLC_TTS_ACCESS_KEY=
VOLC_TTS_ACCESS_TOKEN=
VOLC_TTS_RESOURCE_ID=seed-tts-1.0
VOLC_TTS_VOICE_TYPE=zh_female_wanwanxiaohe_moon_bigtts
SPEECH_TTS_VENDOR=bytedance
MIMO_API_KEY=
MIMO_TTS_MODEL=mimo-v2.5-tts
MIMO_TTS_VOICE=茉莉
```

- `SPEECH_PROVIDER_MODE=mock`：TTS/ASR 都使用 mock，不需要 key。
- `SPEECH_PROVIDER_MODE=auto|real`：TTS 走火山 V3 `/api/v3/tts/unidirectional`；ASR 优先走火山流式 WebSocket，失败时 fallback mock。
- 如果前端显示“语音识别：演示模式”，先看 `/health` 里的 `providers.speech_provider_mode`
  是否为 `auto` 或 `real`，以及 `providers.volc_asr_configured` 是否为 `true`。
- 火山流式 ASR 鉴权头里的 `X-Api-App-Key` 实际填写控制台 APP ID，`X-Api-Access-Key` 填 Access Token；推荐用 `VOLC_ASR_APP_ID` 和 `VOLC_ASR_ACCESS_TOKEN`，旧字段 `VOLC_ASR_APP_KEY` / `VOLC_ASR_ACCESS_KEY` 仍兼容。
- `VOLC_TTS_ACCESS_KEY` 是火山文档里的 Access Key；如果你已经填了旧字段名 `VOLC_TTS_ACCESS_TOKEN`，后端也会兼容读取。
- `VOLC_TTS_RESOURCE_ID` 默认 `seed-tts-1.0`。如果控制台给你的资源 ID 是 `volc.service_type.10029`，就按控制台实际值覆盖。
- 小米 MiMo 只用于 TTS，不接小米 ASR；ASR 仍走上面的 `/ws/voice` 流式识别链路。
- 正式前端可切换“语音播报：字节 / 小米”。选择小米时，后端用 `MIMO_API_KEY` 调用 MiMo TTS；未配置或失败会 fallback mock。
- `/api/speech/tts` 限制 300 字以内，避免浪费 TTS 额度。
- 密钥只在后端读取，不会暴露给 `/test-console`。

## 模型与服务初步选型

- LLM/视觉：七牛云 MaaS。
  - 快速对话与视觉：Doubao-Seed 1.6 Flash。
  - 任务 Agent 与复杂决策：DeepSeek-V4-Flash。
- ASR：火山方舟大模型流式语音识别。
- TTS：豆包语音合成大模型 1.0，前端可选小米 MiMo TTS。
  - 音色 ID：`zh_female_wanwanxiaohe_moon_bigtts`。

## 关键原则

- 演示主线只围绕一顿饭闭环，不堆散功能。
- Agent 输出结构化 JSON，前端只渲染有限状态和 `ui_patch`。
- P0 控制指令由本地状态机处理，不调用大模型。
- Memory、Inventory、Tool Events、Terminal State 必须真实落库。
- 视觉、语音、模型 provider 支持 `mock / hybrid / real` 模式，保证线上答辩可复现。

## 赛前上线检查

1. 确认 `git status --short` 只包含本轮准备提交，且 `.env`、`data/`、生成媒体不在提交列表。
2. 启动后端并访问 `/health`，real 全链路演示时需看到 Qiniu、vision、Volc ASR/TTS 配置均为 `true`。
3. 依次运行 `pytest backend/tests`、`npm run build`、`mock-demo`、`hybrid-smoke`、`speech-smoke`、`voice-smoke`。
4. 如果 `hybrid-smoke` 或 `voice-smoke` 失败，现场主流程切回 `DEMO_MODE=mock`、`SPEECH_PROVIDER_MODE=mock`；real provider 只作为加分片段展示。
