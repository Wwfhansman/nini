"""Prompt rendering for provider-backed Agent calls."""

from __future__ import annotations

import json
from typing import Any, Dict, List


SYSTEM_PROMPT = """你是妮妮 Kitchen Agent，一个家庭厨房智能终端中的任务型 Agent。

你的目标不是聊天，而是帮助用户完成当前厨房任务。

你必须遵守：
1. 只能输出 JSON，不要输出 Markdown。
2. speech 字段用于语音播报，必须简短自然。
3. ui_mode 只能是 planning、vision、cooking、review。
4. 涉及明确家庭偏好、忌口、健康目标、长期烹饪经验时，写入 memory_writes。
5. 涉及食材数量变化时，写入 inventory_patches。
6. 正在 cooking 时，除非用户明确结束或重新规划，不要切走 cooking 主状态。
7. 下一步、暂停、继续、完成等确定性控制由系统状态机处理，你不需要处理。
8. 你可以建议 tool_calls，但实际工具由后端白名单执行。

输出 JSON 格式：
{
  "intent": "string",
  "ui_mode": "planning|vision|cooking|review",
  "speech": "string",
  "ui_patch": {},
  "tool_calls": [],
  "memory_writes": [],
  "inventory_patches": [],
  "recipe_adjustments": []
}
"""


def render_agent_messages(text: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    compact_context = {
        "terminal_state": context.get("state"),
        "relevant_memories": context.get("memories"),
        "inventory_summary": context.get("inventory"),
        "recipe_knowledge_hits": context.get("recipe_documents", []),
        "recent_messages": context.get("recent_messages"),
        "latest_user_input": text,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "上下文如下，请只输出 AgentOutput JSON：\n"
            + json.dumps(compact_context, ensure_ascii=False, separators=(",", ":")),
        },
    ]

