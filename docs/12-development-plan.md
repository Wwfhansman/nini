# 开发进程规划

## 总体策略

后端先行，临时测试页调通，正式前端最后做。

开发顺序：

```text
文档与任务拆解
  -> 后端基础设施
  -> 数据库和状态机
  -> skills
  -> mock providers
  -> Agent runtime
  -> 临时测试页
  -> real providers
  -> 正式前端
  -> 联调与录制
  -> PPT/文档收尾
```

## 阶段 0：项目初始化

目标：

- 建立新仓库。
- 建立后端/前端/文档目录。
- 配置环境变量模板。

产物：

- `README.md`
- `.env.example`
- `backend/`
- `frontend/`
- `docs/`

完成标准：

- 能启动空 FastAPI。
- 能运行基础健康检查。

## 阶段 1：后端基础与数据库

任务：

- `config.py`
- `database.py`
- 初始化 SQLite 表。
- 写 seed/reset 方法。

涉及表：

- terminals。
- memories。
- inventory_items。
- terminal_state。
- tool_events。
- conversations。
- recipe_documents。

完成标准：

- `GET /api/state` 能返回默认状态。
- reset 后数据可复现。

## 阶段 2：状态机

任务：

- 实现 `terminal/state.py`。
- 实现 control commands。
- 记录 local_control events。

接口：

- `POST /api/control`

完成标准：

- start -> cooking。
- next_step 更新步骤。
- pause/resume 更新计时状态。
- finish -> review。
- 所有 control 都记录 `model_called=false`。

## 阶段 3：Skills

任务：

- memory write/search/export。
- inventory upsert/deduct/summary。
- recipe plan/adjust/review。
- vision observation normalization。

完成标准：

- 输入家庭约束后，memory 和 inventory 真实写入。
- 视觉 observation 能修正库存。
- recipe 能根据“不喜欢太酸”调整步骤。

## 阶段 4：Mock Providers

任务：

- `mocks/agent_responses.py`
- `mocks/vision_responses.py`
- `DEMO_MODE=mock`

完成标准：

- 不配置任何 API key 也能跑完整 demo script。

## 阶段 5：Agent Runtime

任务：

- Pydantic schemas。
- prompt builder。
- provider call。
- JSON parse/validate/fallback。
- skill executor。

接口：

- `POST /api/chat`

完成标准：

- chat 可触发 planning。
- “记住我不喜欢太酸”可写 memory 并调整 cooking step。
- 模型输出失败时不破坏状态。

## 阶段 6：临时测试页

任务：

- 建立 test console。
- 支持 chat、vision、control、state、export。
- 提供 `scripts/run_mock_demo.py` 命令行验证完整 mock 流程。

完成标准：

- 能用测试页完整跑通 demo script。
- 后端日志、数据库、tool_events 与预期一致。
- demo runner 能在本地 FastAPI 上验证 planning、vision、cooking、memory update、review 和 memory export。

## 阶段 7：真实模型接入

任务：

- 七牛 MaaS provider。
- Doubao vision。
- DeepSeek agent。
- provider logs。

完成标准：

- `DEMO_MODE=hybrid` 可运行。
- 模型输出经过 schema 校验。
- 出错可 fallback mock。

## 阶段 8：语音接入

任务：

- 火山 ASR。
- 火山 TTS。
- 前端录音或上传音频。
- 播放 TTS。

完成标准：

- ASR 得到文本后走 `/api/chat`。
- TTS 可播放 `speech`。
- 语音失败时文本流程不受影响。

## 阶段 9：正式前端

任务：

- React + Vite。
- StatusBar。
- Workspace。
- Planning/Vision/Cooking/Review views。
- Sidebar。
- ChatBar。
- ToolTimeline。

完成标准：

- 正式界面完整跑 demo。
- UI 体现厨房终端，不像普通聊天页。
- 中间主工作台只展示当前最重要动作。

## 阶段 10：联调与材料

任务：

- 录制 mock 稳定版演示。
- 录制 hybrid/real 片段作为加分。
- 完成 PPT。
- 完成 README 和运行说明。
- 完成答辩 Q&A。

完成标准：

- 无 API key 也能跑 mock demo。
- 配置 API key 后能跑真实 provider。
- 演示视频 3-5 分钟。

## Coding Agents 分工建议

Agent A：数据库、schema、状态机。  
Agent B：memory、inventory、recipe skills。  
Agent C：Agent runtime、prompt、provider 抽象。  
Agent D：临时测试页和 API 联调。  
Agent E：七牛和火山 provider。  
Agent F：正式前端 UI。  
Agent G：文档、README、PPT 素材、demo script。  
Agent H：测试、mock 数据、端到端验证。

## 每日节奏建议

### Day 1

- 项目初始化。
- 数据库。
- 状态机。
- API skeleton。

### Day 2

- memory/inventory/recipe skills。
- mock providers。
- `/api/chat` 初版。

### Day 3

- 临时测试页。
- 跑通完整 mock demo。
- 修正数据模型。

### Day 4

- 七牛 MaaS provider。
- DeepSeek agent JSON 输出。
- Doubao vision real/hybrid。

### Day 5

- 火山 ASR/TTS。
- 正式前端开始。
- 保留文本兜底。

### Day 6

- 正式前端联调。
- 录制演示视频。
- 修 UI 细节和状态展示。

### Day 7

- PPT。
- 文档补齐。
- 源码整理。
- 准备答辩 Q&A。

## 风险控制

必须随时可切回：

```text
DEMO_MODE=mock
```

每个阶段都要保证主线可运行，不要等最后一天才集成。
