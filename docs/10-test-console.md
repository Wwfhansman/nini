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
