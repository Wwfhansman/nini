# 实现检查清单

这份清单按依赖顺序排列，用于分配给 coding agents 或自己逐项验收。

## 0. 项目骨架

- [ ] 创建 `backend/`。
- [ ] 创建 `frontend/`。
- [ ] 创建 `frontend-test/` 或 `/test-console`。
- [ ] 加入 `.env.example`。
- [ ] 加入基础 README 运行说明。
- [ ] 建立 `data/` 目录并忽略本地数据库文件。

验收：

- [ ] `./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload` 可启动。
- [ ] `GET /health` 返回正常。

## 1. 数据库

- [ ] 实现 `backend/database.py`。
- [ ] 创建 `terminals`。
- [ ] 创建 `memories`。
- [ ] 创建 `inventory_items`。
- [ ] 创建 `terminal_state`。
- [ ] 创建 `tool_events`。
- [ ] 创建 `conversations`。
- [ ] 创建 `recipe_documents`。
- [ ] 实现 `init_db()`。
- [ ] 实现 demo seed/reset。

验收：

- [ ] reset 后默认 `terminal_id=demo-kitchen-001` 可用。
- [ ] `GET /api/state` 返回默认状态。

## 2. Schema

- [ ] `AgentOutput`。
- [ ] `TerminalState`。
- [ ] `RecipePlan`。
- [ ] `CookingStep`。
- [ ] `MemoryWrite`。
- [ ] `InventoryPatch`。
- [ ] `ToolEvent`。
- [ ] API request/response schemas。

验收：

- [ ] 无效 Agent JSON 会被拦截。
- [ ] response 结构统一为 `ok/data/state/events/error`。

## 3. 状态机

- [ ] `start`。
- [ ] `next_step`。
- [ ] `previous_step`。
- [ ] `pause`。
- [ ] `resume`。
- [ ] `finish`。
- [ ] `reset`。
- [ ] control events 写入 `tool_events`。

验收：

- [ ] 所有 P0 控制都不调用模型。
- [ ] 右侧时间线能显示 `model_called=false`。

## 4. Skills

### Memory

- [ ] `memory_write`。
- [ ] `memory_search`。
- [ ] `export_memory_markdown`。

### Inventory

- [ ] `inventory_update`。
- [ ] `inventory_summary`。
- [ ] `inventory_deduct_by_recipe`。

### Recipe

- [ ] 主菜谱模板：低脂不辣番茄鸡胸肉滑蛋。
- [ ] 根据减脂目标调整油和糖。
- [ ] 根据不吃辣移除辣味元素。
- [ ] 根据不喜欢酸调整番茄和鸡蛋比例。
- [ ] 根据视觉结果调整份量。
- [ ] 生成 review。

### Vision

- [ ] mock vision provider。
- [ ] real vision provider 接口。
- [ ] observation 标准化。

验收：

- [ ] 视觉识别结果会改变库存和菜谱。
- [ ] “不喜欢太酸”会改变当前步骤。

## 5. Agent Runtime

- [ ] P0 router。
- [ ] context builder。
- [ ] prompt renderer。
- [ ] model provider abstraction。
- [ ] JSON parse。
- [ ] Pydantic validation。
- [ ] fallback。
- [ ] skill execution。
- [ ] state patch apply。
- [ ] conversations 记录。

验收：

- [ ] `/api/chat` 能完成规划。
- [ ] `/api/chat` 能完成 memory 写入和当前菜谱调整。
- [ ] provider 失败时不破坏状态。

## 6. API

- [ ] `GET /health`。
- [ ] `POST /api/chat`。
- [ ] `POST /api/vision`。
- [ ] `POST /api/control`。
- [ ] `GET /api/state`。
- [ ] `GET /api/export/memory`。
- [ ] `POST /api/knowledge/recipe`。
- [ ] `POST /api/speech/asr`。
- [ ] `POST /api/speech/tts`。

验收：

- [ ] Postman 或临时测试页可跑完整流程。

## 7. 临时测试页

- [x] terminal_id 输入。
- [x] chat 输入。
- [x] 上传图片。
- [x] control buttons。
- [x] state JSON 面板。
- [x] memories 面板。
- [x] inventory 面板。
- [x] tool_events 面板。
- [x] export memory 展示。
- [x] 一键 mock demo 流程。
- [x] `scripts/run_mock_demo.py` 命令行验证。

验收：

- [x] 不依赖正式前端即可录制后端闭环。

## 8. Real Providers

### Qiniu MaaS

- [x] chat JSON。
- [x] vision。
- [x] model config。
- [x] timeout。
- [x] provider logs。

### Volcengine ASR

- [x] 录音上传版本。
- [ ] 流式版本可后续。

### Volcengine TTS

- [x] 传入 speech。
- [x] 返回前端可播放音频。
- [x] 音色 `zh_female_wanwanxiaohe_moon_bigtts`。

验收：

- [x] `DEMO_MODE=hybrid` 可跑。
- [x] `DEMO_MODE=mock` 永远可跑。
- [x] `SPEECH_PROVIDER_MODE=mock` 永远可跑。

## 9. 正式前端

位于 `frontend/`，React + Vite，普通 CSS，无外部 CDN，API 通过 `VITE_API_BASE_URL` 注入。

- [x] TopBar（StatusBar）。
- [x] CenterPanel（Workspace 路由）。
- [x] PlanningView。
- [x] VisionView。
- [x] CookingView。
- [x] ReviewView。
- [x] RightPanel（Sidebar）。
- [x] ToolTimeline。
- [x] MemoryPanel。
- [x] InventoryPanel。
- [x] LeftPanel（ChatBar）。
- [x] SpeechControls。
- [x] Run Demo 按钮（一键演示流程）。
- [x] 终端 ID 在 TopBar 可改。

验收：

- [x] `npm install` 与 `npm run build` 通过。
- [x] UI 不像聊天页，三栏布局保留原型视觉风格。
- [x] 中间主工作台清晰展示当前动作。
- [x] 右侧时间线清楚展示 Agent/状态机工作过程，P0 控制显示 `LOCAL · 未调用模型`。
- [x] 启动方式：`cd frontend && npm install && npm run dev`，默认 `http://127.0.0.1:5173`。

## 10. 演示与提交

- [ ] mock 版演示视频。
- [ ] hybrid/real 片段。
- [ ] PPT。
- [x] README 运行说明。
- [ ] 架构图。
- [ ] 答辩 Q&A。
- [ ] 源码整理。

验收：

- [ ] 无 API key 能跑 mock。
- [ ] 配置 API key 能跑真实 provider：
  - [ ] `/health` 显示 Qiniu、vision、Volc ASR/TTS 均已配置。
  - [ ] `hybrid-smoke --timeout 60` 看到 `qiniu_chat` 成功且 `fallback_used=false`。
  - [ ] `speech-smoke --timeout 60` 看到 TTS 成功且 `fallback_used=false`。
  - [ ] `voice-smoke --timeout 60` 看到 `volc_streaming_asr` 启动且 `fallback_used=false`。
- [ ] 视频中清楚展示三大高光：
  - [ ] 现实食材打断计划。
  - [ ] 记忆立即改变步骤。
  - [ ] P0 指令不走模型。

## 11. 上线前本地验收顺序

这组命令用于比赛演示前最终检查。先保留 mock 主线，再检查 real 加分片段。

```bash
./.venv/bin/pytest backend/tests
cd frontend && npm run build
```

后端启动后：

```bash
./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
./.venv/bin/python scripts/run_mock_demo.py --mode hybrid-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
./.venv/bin/python scripts/run_mock_demo.py --mode speech-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
./.venv/bin/python scripts/run_mock_demo.py --mode voice-smoke --timeout 60 --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

兜底标准：

- `mock-demo` 必须通过，作为现场主线。
- real/hybrid smoke 任一失败时，不阻塞 mock 演示；只取消对应加分片段。
- 发布前再次确认 `.env`、`data/`、日志、录屏原始文件未进入 git。
