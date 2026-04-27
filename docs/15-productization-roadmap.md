# 产品化功能改造方案

## 目标

当前项目已经具备后端状态机、Agent runtime、真实 provider、语音接口和正式前端。下一阶段目标不是继续堆技术点，而是把它从“可演示 demo”推进到“可体验产品”：

- 核心流程能通过自然语言完成。
- 屏幕只承担状态反馈、任务进程和确认展示。
- 按钮保留为兜底，不再是主交互路径。
- 开发者信息收敛为产品化状态文案。
- mock、hybrid、real 三种模式都能稳定完成演示。

产品口径：

```text
妮妮 Kitchen Agent 是一个家庭厨房 AI 终端。
它不是手机 App，也不是普通聊天机器人，而是通过语音、视觉、记忆和工具调用接管厨房中的日常决策与烹饪陪伴。
```

## 当前状态

已具备：

- FastAPI 后端、SQLite 数据隔离、terminal state。
- P0 本地状态机：start、next_step、previous_step、pause、resume、finish、reset。
- Agent runtime、memory、inventory、recipe、vision、knowledge skills。
- 七牛 MaaS provider、火山 TTS/ASR 接口、mock fallback。
- React/Vite 正式前端，含 planning、vision、cooking、review 四态。
- ToolTimeline 展示 Agent 工作流，Memory/Inventory 展示状态变化。
- `/test-console` 与 `scripts/run_mock_demo.py` 作为后端调试兜底。

主要缺口：

- 语音仍偏“上传音频测试”，不是自然语音会话。
- 视觉仍偏“上传图片”，产品口径还没有完全变成“终端看食材”。
- memory 能写入但缺少管理、确认和纠错能力。
- Provider 状态、DEMO_MODE、fallback 等文案偏开发者。
- 演示脚本仍依赖按钮推动，voice-first 叙事不够强。

## 产品化原则

### 语音优先

所有核心操作都必须有自然语言等价路径：

| 操作 | 自然语言 |
|---|---|
| 规划晚餐 | “今晚吃什么”“帮我安排一顿晚饭” |
| 看食材 | “看看台面上有什么”“看一下食材” |
| 开始烹饪 | “就做这个”“开始做这道” |
| 下一步 | “下一步”“好了”“然后呢” |
| 暂停 | “等一下”“先暂停” |
| 继续 | “继续”“我回来了” |
| 重复步骤 | “再说一遍”“这一步怎么做” |
| 调整口味 | “少放辣”“别太酸”“少油一点” |
| 写入记忆 | “记住我不喜欢太酸”“以后默认少油” |
| 删除/修正记忆 | “刚才那个记错了”“不要记妈妈不吃辣了” |
| 完成复盘 | “做完了”“这次太咸了，下次少放盐” |

### 状态感知

同一句话在不同状态下含义不同。后端意图路由必须带上当前 `ui_mode`、`current_step_index`、recipe、memories、inventory 和 recent events。

示例：

```text
“好了”
planning -> 确认方案并进入 cooking
cooking -> next_step
review -> 结束本次复盘
```

### 本地优先

确定性 P0 命令先走本地规则，不调用 LLM：

```text
开始、下一步、上一步、暂停、继续、完成、重置、再说一遍
```

复杂语义才交给 Agent：

```text
“妈妈今天也吃，别放辣”
“这一步能不能用空气炸锅”
“番茄只有半个，还够吗”
```

### 隐私可解释

产品文案需要明确：

```text
待机态只做本地唤醒/手动开启，不上传环境音。
会话态只上传检测到的有效语音片段。
烹饪态短时间保持语音会话，超时回到待命。
```

Web Demo 暂用“开启语音模式”模拟终端授权。

## 目标交互链路

```text
用户说话
  -> 前端录音
  -> /api/speech/asr
  -> 后端 voice intent router
  -> P0 local control 或 Agent runtime
  -> state/events/memory/inventory 更新
  -> 前端刷新工作台和任务时间线
  -> /api/speech/tts
  -> 自动播报
```

屏幕反馈：

- 顶部：语音状态、当前模式、终端状态。
- 左侧：用户语音转写和妮妮回复。
- 中间：当前任务主视图。
- 右侧：Agent 工作流、记忆和库存变化。

## 前端改造

### 1. 语音会话模式

新增一个产品化入口：

```text
开启语音模式
```

状态：

- 语音待命。
- 正在听。
- 识别中。
- 理解中。
- 播报中。

第一版实现：

- 使用 `MediaRecorder`。
- 点击开始/停止录音。
- 录音结束自动调用 `/api/speech/asr`。
- ASR 文本自动调用 `/api/chat`。
- `/api/chat` 返回 speech 后自动调用 `/api/speech/tts` 播放。

第二版增强：

- 加入简单 VAD 或音量阈值自动分段。
- 无语音超时后回到待命。
- TTS 播放时暂停录音，避免自我回声。

### 2. 状态提示语

每个主状态显示“你可以说”提示，降低纯语音学习成本。

planning：

```text
“今晚吃什么”
“我最近减脂”
“妈妈不吃辣”
“看看食材”
```

vision：

```text
“确认这些食材”
“重新看一下”
“按这些调整菜谱”
```

cooking：

```text
“下一步”
“暂停一下”
“继续”
“这一步再说一遍”
“少放点油”
```

review：

```text
“做完了”
“这次太酸了”
“下次少放盐”
“导出家庭记忆”
```

### 3. 视觉入口产品化

把“上传图片”改成“看看食材”。

Web Demo 仍然弹出文件选择，但界面和答辩口径表达为：

```text
终端摄像头采集当前台面画面。
```

视觉流程：

```text
用户说“看看食材”
  -> 前端进入 vision 态
  -> Web Demo 选择图片
  -> /api/vision
  -> 展示识别结果
  -> 用户说“确认”
  -> 写入库存并调整菜谱
```

### 4. 开发者文案收敛

保留调试信息，但换成产品语言：

| 当前文案 | 产品文案 |
|---|---|
| DEMO_MODE | 智能服务 |
| mock | 演示模式 |
| hybrid | 混合模式 |
| real | 在线模式 |
| provider fallback | 已启用本地兜底 |
| provider logs | 服务状态 |
| model_called=false | 本地即时响应 |

详细 provider logs 只放在 `/test-console` 或隐藏调试区。

## 后端改造

### 1. Voice Intent Router

新增或增强语音意图路由模块：

```text
backend/agent/voice_router.py
```

职责：

- 规范化 ASR 文本。
- 识别 P0 本地命令。
- 根据 `ui_mode` 做状态感知映射。
- 对复杂意图返回 Agent runtime 输入。
- 返回可解释 `intent`、`command`、`confidence`。

建议返回结构：

```json
{
  "route": "local_control",
  "intent": "next_step",
  "command": "next_step",
  "confidence": 0.96,
  "reason": "cooking 状态下“好了”表示进入下一步"
}
```

### 2. P0 命令扩展

当前已有：

```text
start / next_step / previous_step / pause / resume / finish / reset
```

建议新增：

- `repeat_current_step`：不改变状态，只播报当前步骤。
- `confirm`：用于视觉确认、记忆删除确认、方案确认。
- `cancel`：取消当前确认。

自然语言映射：

```text
“再说一遍”“这一步怎么做” -> repeat_current_step
“确认”“可以”“按这个来” -> confirm
“算了”“取消”“不用了” -> cancel
```

### 3. 记忆管理

在 memory skill 增加：

- memory list/search 已有则复用。
- memory delete by id/key。
- memory update。
- pending confirmation。

高风险操作要确认：

```text
用户：“不要记妈妈不吃辣了”
妮妮：“确认删除‘妈妈不吃辣’这条家庭记忆吗？”
用户：“确认”
系统删除
```

### 4. 视觉确认

当前 vision 可直接更新库存和菜谱。产品化后建议增加确认语义：

第一阶段为了演示稳定，可以保留自动写入，但前端文案显示“已根据识别结果调整”。
第二阶段再引入 pending confirmation。

### 5. TTS 自动播报策略

不是所有后端响应都要播报长文本。

建议规则：

- local control：播报短句，例如“进入下一步”。
- planning：播报菜名和核心理由，不读完整步骤。
- cooking：播报当前步骤标题和一句操作说明。
- memory write：播报“我记住了”。
- provider fallback：不播报技术错误，只播报“我先用本地方案继续”。

## API 调整建议

保留现有 API，不做破坏性改动。

新增可选接口：

```text
POST /api/voice/turn
```

作用：把 ASR 文本、source、auto_tts 统一成一次语音轮次。

请求：

```json
{
  "terminal_id": "demo-kitchen-001",
  "text": "好了",
  "source": "voice",
  "auto_tts": true
}
```

响应沿用 `ApiResponse`，额外包含：

```json
{
  "voice_route": {
    "route": "local_control",
    "intent": "next_step",
    "command": "next_step"
  },
  "tts_hint": {
    "should_speak": true,
    "text": "进入下一步。"
  }
}
```

如果时间紧，也可以先复用 `/api/chat`，只在内部增强 voice router。

## 开发阶段

### 阶段 A：语音闭环

目标：从“上传音频”升级为“录音 -> ASR -> chat/control -> TTS 自动播报”。

任务：

- 前端 `MediaRecorder` 录音组件。
- ASR 成功后自动发送文本。
- 回复后自动 TTS。
- 顶部语音状态正确变化。

验收：

- 用户无需输入文字即可完成一次规划对话。
- TTS 播报结束后回到待命。
- ASR/TTS 失败时文本流程不受影响。

### 阶段 B：P0 自然语言控制

目标：烹饪核心控制可纯语音完成。

任务：

- 扩展 P0 router。
- 新增 `repeat_current_step`。
- 增加状态感知测试。
- ToolTimeline 显示“本地即时响应”。

验收：

- “好了”在 cooking 下触发 next_step。
- “等一下”触发 pause。
- “我回来了”触发 resume。
- “这一步再说一遍”不改变 step，只返回当前步骤播报。
- 所有 P0 控制 `model_called=false`。

### 阶段 C：视觉语音触发

目标：视觉从上传功能变成厨房终端能力。

任务：

- 前端把入口改为“看看食材”。
- 用户说“看看食材”后进入 vision 态。
- Web Demo 弹出图片选择。
- 识别后展示 before/after。

验收：

- 语音触发视觉流程。
- 识别结果更新库存和菜谱。
- 右侧时间线显示 vision_observe、inventory_update、recipe_adjust。

### 阶段 D：记忆管理

目标：memory 不只是写入，还能解释、修正、删除。

任务：

- 增加 memory delete/update skill。
- 前端记忆卡支持展示来源和最近更新时间。
- 高风险删除用语音确认。

验收：

- “记住我不喜欢太酸”写入 preference。
- “刚才那个记错了”进入纠错流程。
- “不要记妈妈不吃辣了”需要确认后删除。

### 阶段 E：界面产品化

目标：答辩界面减少开发者感，强化生活终端感。

任务：

- 顶部状态产品化。
- Provider 信息收敛为服务状态。
- 每个 ui_mode 增加“你可以说”提示。
- 一键 Demo 保留但弱化为演示辅助。
- 移除或隐藏过多 raw status。

验收：

- 第一屏看起来像厨房终端，不像开发控制台。
- 用户知道当前能说什么。
- 右侧 Agent 工作流能清楚展示智能体工作过程。

### 阶段 F：真实链路打磨

目标：录制稳定视频和答辩现场稳定演示。

任务：

- mock 全流程录制。
- real/hybrid 关键片段录制。
- provider timeout 和 fallback 文案优化。
- 完成答辩 Q&A 中隐私、成本、延迟问题的回答。

验收：

- mock 模式 100% 可复现。
- real 模式至少能展示一次真实规划、一次真实 TTS、一次真实 vision。
- 失败时不暴露技术错误给用户。

## 推荐开发顺序

```text
1. 前端语音录音闭环
2. 后端 P0 自然语言控制扩展
3. 自动 TTS 播报
4. “你可以说”提示语和界面产品化
5. 视觉语音触发
6. memory 删除/纠错
7. provider/fallback 产品化文案
8. 录制脚本和答辩材料
```

## 最终演示脚本

目标是几乎全语音：

```text
妮妮，今晚帮我安排一顿晚饭，我最近减脂，妈妈不吃辣。
看看我现在有哪些食材。
就做这个。
下一步。
等一下。
继续。
这一步再说一遍。
记住我不喜欢太酸。
做完了。
```

展示点：

- Agent 工作流实时滚动。
- 家庭记忆写入和命中。
- 视觉识别改变库存与菜谱。
- P0 指令本地即时响应，不走模型。
- TTS 自动播报，用户不用碰屏幕。
- 复盘生成下次建议。

## 完成定义

产品化阶段完成后，项目应满足：

- 不点按钮也能完成主要演示链路。
- 按钮只作为现场兜底。
- 所有 P0 语音控制响应快且不调用模型。
- 复杂语义能进入 Agent runtime 并写入状态。
- 语音、视觉、记忆、库存、菜谱、烹饪状态形成闭环。
- 前端文案面向普通家庭用户，而不是开发者。
- mock 模式稳定，real 模式可展示真实 AI 服务能力。
