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

- [ ] `uvicorn backend.app:app --reload` 可启动。
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

- [ ] StatusBar。
- [ ] Workspace。
- [ ] PlanningView。
- [ ] VisionView。
- [ ] CookingView。
- [ ] ReviewView。
- [ ] Sidebar。
- [ ] ToolTimeline。
- [ ] MemoryPanel。
- [ ] InventoryPanel。
- [ ] ChatBar。
- [ ] Speech controls。

验收：

- [ ] UI 不像聊天页。
- [ ] 中间主工作台清晰展示当前动作。
- [ ] 右侧时间线清楚展示 Agent/状态机工作过程。

## 10. 演示与提交

- [ ] mock 版演示视频。
- [ ] hybrid/real 片段。
- [ ] PPT。
- [ ] README 运行说明。
- [ ] 架构图。
- [ ] 答辩 Q&A。
- [ ] 源码整理。

验收：

- [ ] 无 API key 能跑 mock。
- [ ] 配置 API key 能跑真实 provider。
- [ ] 视频中清楚展示三大高光：
  - [ ] 现实食材打断计划。
  - [ ] 记忆立即改变步骤。
  - [ ] P0 指令不走模型。
