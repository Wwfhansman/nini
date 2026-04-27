# 前端开发文档

## 开发原则

正式前端最后做。先用临时测试页面调通后端闭环。

正式前端目标不是做管理后台，而是模拟厨房终端：

- 大字号。
- 当前只显示一个动作。
- 控制按钮少。
- 状态常驻。
- 工具调用可见。

## 当前实现

正式前端位于 `frontend/`，技术栈：

- React 18 + Vite 5。
- 普通 CSS（`src/styles.css`），不引入 UI 框架，不依赖外部 CDN。
- 系统字体回退：PingFang SC / Hiragino Sans GB / system-ui。
- 单一 `src/api.js` 集中后端调用，组件不直接 fetch。

`/test-console` 仍然保留，用于调试后端原始事件、跑一键 mock demo、验证 provider 行为。
正式终端 `frontend/` 用于演示和录制视频。

## 启动

```bash
cd frontend
npm install
npm run dev   # http://127.0.0.1:5173
```

## 构建

```bash
cd frontend
npm run build       # 输出 dist/
npm run preview     # 预览 dist/，端口 4173
```

## 配置

为了避免 CORS 问题，前端默认走 **Vite dev/preview proxy**：浏览器始终请求
`http://127.0.0.1:5173`（或 4173），Vite 把以下路径透传到后端：

```text
/api  /health  /test-console  /static
```

`api.js` 默认使用相对路径，因此后端不需要安装 CORS 中间件。

切换上游后端：

```bash
cd frontend
cp .env.example .env
# 默认：
# VITE_API_PROXY_TARGET=http://127.0.0.1:8000
# VITE_DEFAULT_TERMINAL_ID=demo-kitchen-001
# 仅当要把 dist/ 部署到独立域名（且后端开 CORS）时才设置：
# VITE_API_BASE_URL=https://nini.example.com
```

API key 不在前端读取，永远只在后端 `.env` 中持有。

## 目录结构

```text
frontend/
  package.json
  vite.config.js
  index.html
  .env.example
  src/
    main.jsx
    App.jsx               # 顶层状态、API 编排、一键演示
    api.js                # 所有后端 HTTP 调用
    styles.css            # 设计 token + 布局 + 响应式
    components/
      TopBar.jsx          # 品牌、状态、终端 ID、智能服务、语音状态、时钟
      LeftPanel.jsx       # 对话、语音状态条、文本输入、快捷键
      SpeechControls.jsx  # 录音语音闭环 / 上传录音 / 重播回复
      CenterPanel.jsx     # 主工作台路由（按 ui_mode）
      PlanningView.jsx    # 后端 state.recipe + 记忆/库存
      VisionView.jsx      # 食材画面 + observation + 菜谱影响
      CookingView.jsx     # KDS 步骤、计时器（显示层）、控制按钮
      ReviewView.jsx      # 用时、库存、记忆、导出 markdown
      RightPanel.jsx      # ToolTimeline + Memory + Inventory
      ToolTimeline.jsx    # 后端 events 映射成产品化任务进程
      MemoryPanel.jsx     # 家庭记忆条目 + tag 颜色
      InventoryPanel.jsx  # 当前库存 + 服务状态摘要
```

## 页面布局

```text
┌───────────────────────────────────────────────────────────┐
│ TopBar：品牌 / 当前状态 / 终端 ID / 智能服务 / 语音 / 时钟   │
├───────────────────────────────────────────────────────────┤
│ DemoBar：一键演示 / 选择食材画面 / 重置                      │
├──────────────┬───────────────────────────┬────────────────┤
│ LeftPanel    │ CenterPanel               │ RightPanel     │
│ 对话 + 输入   │ planning/vision/cooking/  │ 任务进程        │
│ 语音控件     │ review                    │ 记忆 / 库存     │
└──────────────┴───────────────────────────┴────────────────┘
```

中间工作台按 `state.ui_mode` 切换四个视图，所有数据来自后端响应或 `/api/state`。

## 主工作台状态

### planning

读取：`state.dish_name`、`state.recipe.estimated_minutes`、`state.recipe.servings`、
`state.recipe.ingredients`、`state.active_adjustments`、`memories`、`inventory`。

家庭记忆只在后端 `memories` 命中时显示，**不在初始 planning 写死“用户不喜欢太酸”**。

### vision

- 用户说“看看食材”后，后端返回 `start_vision`，前端进入 vision 态。
- Web 演示中选择一张食材画面，模拟终端摄像头。
- 点击「开始识别」→ `POST /api/vision`。
- 返回的 `observation.ingredients / notes` 渲染为“看到的食材”和观察备注。
- “对菜谱的影响”取自 `state.recipe.servings` 与 `state.active_adjustments`，不再前端写死“番茄半个”。

### cooking

完全以后端 state 为唯一来源：

- `current_step_index`、`recipe.steps[idx]`、`heat`、`ingredients`、`duration_seconds`。
- `timer_status`、`timer_remaining_seconds`、`active_adjustments`。
- 所有控制按钮调用 `POST /api/control`，前端不自行推进步骤。

倒计时仅是显示层动画：每次后端返回新 state 即重置；前端 interval 不会修改后端状态。

### review

显示 `recipe.estimated_minutes`、`recipe.steps.length`、`active_adjustments.length`、
`inventory`、`memories`，并提供「导出家庭记忆卡」→ `GET /api/export/memory`。

## 右侧任务进程

`ToolTimeline` 把后端 `tool_events` + 当前会话累计 events 去重排序，渲染成中文任务节点：

| 后端事件 | 中文任务名 |
|---|---|
| memory_write | 记住家庭偏好 |
| inventory_update | 更新食材库存 |
| recipe_plan | 生成晚餐方案 |
| recipe_adjust | 调整烹饪方案 |
| start_vision | 准备查看食材 |
| vision_observe | 识别食材画面 |
| speech_tts | 生成语音回复 |
| speech_asr | 理解语音输入 |
| provider_call | 智能服务响应 |
| provider_error / vision_provider_fallback | 启用本地兜底 |
| start / next_step / previous_step / pause / resume / finish / reset / repeat_current_step | 本地即时响应 |

判定“本地即时响应”：`event_type === 'local_control'` 或 `output.model_called === false`。
状态条着色：已完成灰、最新动作 terra、本地兜底/需要处理红。

## SpeechControls

- 主入口：浏览器 `MediaRecorder` 录音，点击开始/停止后自动走
  `/api/speech/asr` → `/api/chat` → `/api/speech/tts`。
- 上传录音：保留本地音频文件上传兜底，识别后复用同一条 voice turn。
- 重播回复：对最近一条妮妮回复调用 `POST /api/speech/tts`，返回 `audio_base64`
  即播放；mock 或 fallback 时保留文字回复。
- 语音状态：待命、请求麦克风、正在听、识别中、理解中、播报中、需要处理。
- 不做实时流式 ASR、不做打断。

## 一键演示按钮

按演示脚本依次调用：

```text
reset → /api/chat 家庭约束 → (可选) /api/vision → start
→ /api/chat 不喜欢太酸 → next_step → pause → resume → finish → /api/export/memory
```

每步之间 600–800ms 延迟，便于右侧任务进程呈现“在动”的感觉。
若用户没选食材画面，跳过视觉一步并提示。

## 视觉风格

延续 Claude Design 原型：暖米色背景、黑色顶部栏、赤陶橙 / 琥珀 / 草绿色强调色、
三栏布局、KDS 大字号烹饪态、时间线节点。系统字体替代 Google Fonts，无外链请求。

## 错误与加载

- `loading=true` 时按钮禁用，发送按钮显示「思考中…」。
- 顶部出现红色 banner 显示 API 错误信息，可手动关闭。
- 本地兜底体现在右侧任务进程（红色边框）和库存面板下方的服务状态。
- 不使用 `alert`。

## 前端完成标准

- 能完整跑一键演示。
- P0 控制即时反馈、右侧时间线显示“本地即时响应”。
- memory 与 inventory 的变化随后端响应即时更新。
- vision 结果改变 planning/cooking。
- review 能回扣整个闭环并导出记忆 markdown。
