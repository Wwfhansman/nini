# 前端开发文档

## 开发原则

正式前端最后做。先用临时测试页面调通后端闭环。

正式前端目标不是做管理后台，而是模拟厨房终端：

- 大字号。
- 当前只显示一个动作。
- 控制按钮少。
- 状态常驻。
- 工具调用可见。

## 技术栈

建议：

- React + Vite。
- 普通 CSS。
- 不引入复杂 UI 组件库。

## 页面布局

```text
┌──────────────────────────────────────────────┐
│ 顶部状态栏：妮妮 Kitchen Agent / 终端 / 状态 │
├──────────────────────────────┬───────────────┤
│                              │ 右侧栏        │
│ 中间主工作台                  │ - 技能时间线   │
│ planning/vision/cooking/review│ - 记忆命中     │
│                              │ - 库存摘要     │
├──────────────────────────────┴───────────────┤
│ 底部输入区：文本、语音、上传图片、控制按钮    │
└──────────────────────────────────────────────┘
```

## 主工作台状态

### planning

展示：

- 菜名。
- 推荐理由。
- 食材匹配。
- 预计时间。
- 调整建议。
- “开始做”按钮。

### vision

展示：

- 上传图片预览。
- 识别到的食材。
- 现实冲突。
- 对计划的影响。

重点：视觉不是孤立结果，要显示它如何改变计划。

### cooking

展示：

- 第几步/共几步。
- 当前动作。
- 用料。
- 火候。
- 计时器。
- 下一步/暂停/继续/完成。
- 当前步骤改动标记。

### review

展示：

- 总用时。
- 库存扣减。
- 写入记忆。
- 下次建议。
- 导出记忆卡片。

## 右侧栏

### 技能时间线

按时间倒序或正序：

```text
memory_write
inventory_update
recipe_plan
vision_observe
recipe_adjust
local_control: next_step，未调用模型
```

### 记忆命中

显示当前被用到的 memory：

- 妈妈不吃辣。
- 用户减脂。
- 用户不喜欢太酸。

### 库存摘要

显示：

- 鸡胸肉：少量。
- 番茄：半个。
- 鸡蛋：2 个。

## 底部输入区

控件：

- 文本输入。
- 发送按钮。
- 上传图片按钮。
- 语音录制按钮。
- 开始/下一步/暂停/继续/完成按钮。

语音失败时文本输入必须可完成全部演示。

## 前端状态来源

前端不自行推导业务状态。

所有渲染来自：

- `/api/state`
- `/api/chat`
- `/api/vision`
- `/api/control`

## 组件建议

```text
src/
  App.jsx
  api.js
  components/
    StatusBar.jsx
    Workspace.jsx
    PlanningView.jsx
    VisionView.jsx
    CookingView.jsx
    ReviewView.jsx
    Sidebar.jsx
    ChatBar.jsx
    ToolTimeline.jsx
    InventoryPanel.jsx
    MemoryPanel.jsx
```

## 视觉风格

建议：

- 清爽、实用、厨房终端感。
- 避免营销首页风。
- 避免大段介绍文字。
- 中间内容优先满足“站在厨房远处也看得清”。

## 前端完成标准

- 能完整跑 demo script。
- P0 控制即时反馈。
- 右侧时间线能证明工具调用。
- memory 和 inventory 的变化可见。
- vision 结果能影响 planning/cooking。
- review 能回扣整个闭环。
