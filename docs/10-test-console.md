# 临时测试页面方案

## 为什么需要临时测试页

正式前端最后做。前期必须先用临时测试页把后端闭环调通，避免同时调 UI 和业务逻辑。

临时测试页不是省赛正式界面，但必须能完成：

- chat 输入。
- vision 上传。
- control 操作。
- state 查看。
- tool_events 查看。
- memory/inventory 查看。

## 路径建议

```text
frontend-test/
  index.html
```

或由 FastAPI 静态挂载：

```text
/test-console
```

当前实现采用 FastAPI 静态页面：

```text
backend/static/test-console.html
```

启动后端后访问：

```text
http://127.0.0.1:8000/test-console
```

临时测试页不是正式前端，不承担最终视觉设计和交互体验，只用于后端闭环调试、演示录制和 API 可观测性检查。

## 页面结构

```text
左侧：操作区
  - terminal_id
  - 文本输入
  - 发送 chat
  - 上传图片
  - control buttons

中间：state JSON
  - terminal_state
  - current recipe
  - current step

右侧：调试信息
  - memories
  - inventory
  - tool_events
  - raw response
```

## 必须支持的操作

### 发送 chat

默认填充：

```text
我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？
```

### 上传 vision

选择图片，调用 `/api/vision`。

### 控制按钮

- start。
- next_step。
- pause。
- resume。
- finish。
- reset。

### 导出记忆

调用 `/api/export/memory` 并显示 Markdown。

### 一键演示流程

测试页提供“一键演示流程”按钮，按顺序调用：

1. `reset`
2. `/api/chat` 初始规划
3. `/api/vision` mock 视觉修正
4. `start`
5. `/api/chat` 写入“不喜欢太酸”
6. `next_step`
7. `pause`
8. `resume`
9. `finish`
10. `/api/export/memory`

如果没有选择图片，页面会上传一个空的 mock 文件；后端当前使用 mock vision，不解析真实图片内容。

## Demo runner

除页面外，还提供命令行验证脚本：

```bash
./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

脚本会输出每一步的 HTTP 状态、`state.ui_mode`、最新事件和关键断言结果，用于快速确认 mock demo 主线仍可复现。

## 调试成功标准

正式前端开工前，临时测试页必须能走完：

1. chat 规划菜品。
2. vision 修正菜谱。
3. start cooking。
4. 记住“不喜欢太酸”并改步骤。
5. next/pause/resume。
6. finish review。
7. export memory。

## 与正式前端关系

临时测试页用于验证后端，不追求美观。

正式前端只在临时测试页通过后开始。正式前端不应重新实现业务逻辑，只消费同一批 API。
