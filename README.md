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

## 本地运行

安装依赖：

```bash
python3 -m venv .venv
./.venv/bin/pip install -r backend/requirements.txt
```

启动后端：

```bash
./.venv/bin/uvicorn backend.app:app --reload
```

启动后可以访问临时测试控制台：

```text
http://127.0.0.1:8000/test-console
```

临时测试控制台用于调通后端闭环和录制 mock 演示，不是正式前端。

运行可复现 mock demo：

```bash
./.venv/bin/python scripts/run_mock_demo.py --base-url http://127.0.0.1:8000 --terminal-id demo-kitchen-001
```

运行测试：

```bash
./.venv/bin/pytest backend/tests
```

## 模型与服务初步选型

- LLM/视觉：七牛云 MaaS。
  - 快速对话与视觉：Doubao-Seed 1.6 Flash。
  - 任务 Agent 与复杂决策：DeepSeek-V4-Flash。
- ASR：火山方舟大模型流式语音识别。
- TTS：豆包语音合成大模型 1.0。
  - 音色 ID：`zh_female_wanwanxiaohe_moon_bigtts`。

## 关键原则

- 演示主线只围绕一顿饭闭环，不堆散功能。
- Agent 输出结构化 JSON，前端只渲染有限状态和 `ui_patch`。
- P0 控制指令由本地状态机处理，不调用大模型。
- Memory、Inventory、Tool Events、Terminal State 必须真实落库。
- 视觉、语音、模型 provider 支持 `mock / hybrid / real` 模式，保证线上答辩可复现。
