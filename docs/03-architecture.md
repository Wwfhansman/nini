# 系统架构

## 架构原则

1. 后端是业务状态唯一来源。
2. 前端只渲染后端返回的有限状态和 `ui_patch`。
3. Agent 不能直接执行任意代码，只能输出结构化 JSON。
4. 工具调用由后端白名单 skill 执行。
5. P0 指令由本地状态机处理，不进大模型。
6. 所有外部 AI provider 支持 mock/hybrid/real 模式。

## 总体架构

```text
Browser Terminal
  - temporary test console
  - final kitchen terminal UI
  - audio capture / image upload / controls

FastAPI Backend
  - API layer
  - Agent runtime
  - Local command router
  - Terminal state manager
  - Skills
  - Speech providers
  - Model providers

SQLite
  - memories
  - inventory_items
  - recipe_documents
  - terminal_state
  - tool_events
  - conversations

External Providers
  - Qiniu MaaS: Doubao-Seed 1.6 Flash, DeepSeek-V4-Flash
  - Volcengine ASR: streaming speech recognition
  - Volcengine TTS: Doubao TTS 1.0
```

## 请求流：普通输入

```text
POST /api/chat
  -> router detects whether P0
  -> if P0: terminal_state handles directly
  -> else build context
  -> agent provider returns JSON
  -> schema validation
  -> skill executor
  -> state update
  -> DB writes
  -> response to frontend
```

## 请求流：视觉输入

```text
POST /api/vision
  -> vision provider mock/real
  -> structured visual_observation
  -> inventory skill updates quantities
  -> recipe skill adjusts plan
  -> terminal_state updates ui_mode and patch
  -> tool_events records trace
  -> response to frontend
```

## 请求流：本地控制

```text
POST /api/control
  -> command router
  -> terminal state machine
  -> update current_step/timer_status/ui_mode
  -> record tool_event local_control
  -> response to frontend
```

## 模块划分

### API Layer

位置：

```text
backend/app.py
```

职责：

- 暴露 REST API。
- 参数校验。
- 调用 runtime、state manager 和 providers。
- 统一返回 `AppResponse`。

### Agent Runtime

位置：

```text
backend/agent/runtime.py
```

职责：

- 组装 prompt 和 context。
- 调用模型 provider。
- 校验结构化输出。
- 调用 skill executor。
- 合并 state diff。

不负责：

- 具体数据库 SQL。
- 具体菜谱规则。
- 前端渲染逻辑。

### Router

位置：

```text
backend/agent/router.py
```

职责：

- 识别 P0 指令。
- 判断是否需要 Agent。
- 判断输入是否简单短回复。

P0 示例：

- 下一步。
- 上一步。
- 暂停。
- 继续。
- 开始。
- 完成。

### Terminal State

位置：

```text
backend/terminal/state.py
```

职责：

- 维护当前工作台状态。
- 维护当前菜谱、步骤、计时器、暂停状态。
- 执行本地控制。
- 生成前端可渲染 state。

### Skills

位置：

```text
backend/skills/
```

首版 skill：

- `memory.py`
- `inventory.py`
- `recipe.py`
- `vision.py`
- `recipe_knowledge.py` 可后续加入。

### Providers

位置：

```text
backend/agent/providers.py
backend/speech/
```

职责：

- 对接七牛 MaaS。
- 对接火山 ASR/TTS。
- 提供 mock/hybrid/real 切换。

## 数据隔离

所有核心表包含 `terminal_id`。

```text
terminal_id = 一台厨房终端的独立身份
```

省赛版本不做完整账号系统，但从数据结构上保留多终端隔离能力。

## 状态模式

主工作台只保留四种 `ui_mode`：

- `planning`
- `vision`
- `cooking`
- `review`

侧栏展示：

- memory。
- inventory。
- tool_events。
- provider status。

## 运行模式

```text
DEMO_MODE=mock
  所有模型和视觉返回固定结果，保证录制稳定。

DEMO_MODE=hybrid
  LLM 使用真实 provider，vision 或 speech 可 mock。

DEMO_MODE=real
  所有 provider 使用真实 API。
```

## 为什么不用复杂架构

省赛版本不需要：

- 微服务。
- 消息队列。
- Kubernetes。
- 多用户权限。
- 插件市场。

这些会增加交付风险，不增加核心演示说服力。
