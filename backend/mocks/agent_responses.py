"""Mock agent outputs for the deterministic backend demo."""

from __future__ import annotations

from typing import Any, Dict

from backend.agent.schemas import AgentOutput


def _current_mode(context: Dict[str, Any]) -> str:
    state = context.get("state") or {}
    return state.get("ui_mode", "planning")


def mock_agent_response(text: str, context: Dict[str, Any]) -> AgentOutput:
    normalized = text.strip()

    if "不喜欢太酸" in normalized and "记住" in normalized:
        return AgentOutput(
            intent="remember_sour_preference",
            ui_mode="cooking" if _current_mode(context) == "cooking" else "planning",
            speech="好，我会把这道菜调得不那么酸。",
            ui_patch={"active_adjustments": ["降低酸度", "增加鸡蛋比例", "不额外加醋"]},
            tool_calls=[{"name": "memory_write"}, {"name": "recipe_adjust"}],
            memory_writes=[
                {
                    "type": "preference",
                    "subject": "user",
                    "key": "taste.sour",
                    "value": "不喜欢太酸",
                    "confidence": 1.0,
                    "source": "user_explicit",
                }
            ],
            recipe_adjustments=[
                {
                    "reason": "user_dislikes_sour",
                    "summary": "降低番茄酸度，增加鸡蛋比例，不加醋。",
                    "changes": ["番茄翻炒时间缩短", "鸡蛋比例增加", "不额外加醋"],
                }
            ],
        )

    if "下次" in normalized and "番茄" in normalized and "注意" in normalized:
        return AgentOutput(
            intent="answer_tomato_memory",
            ui_mode=_current_mode(context),
            speech="下次番茄类菜我会默认降低酸度，增加鸡蛋或豆腐来中和，并继续保持不辣。",
            ui_patch={},
            tool_calls=[{"name": "memory_search"}],
        )

    if "减脂" in normalized and "妈妈" in normalized and "不吃辣" in normalized:
        return AgentOutput(
            intent="plan_recipe",
            ui_mode="planning",
            speech="我建议做低脂不辣番茄鸡胸肉滑蛋。",
            ui_patch={"dish_name": "低脂不辣番茄鸡胸肉滑蛋"},
            tool_calls=[
                {"name": "memory_write"},
                {"name": "inventory_update"},
                {"name": "recipe_plan"},
            ],
            memory_writes=[
                {
                    "type": "health_goal",
                    "subject": "user",
                    "key": "diet.goal",
                    "value": "减脂",
                    "confidence": 1.0,
                    "source": "user_explicit",
                },
                {
                    "type": "allergy_or_restriction",
                    "subject": "mother",
                    "key": "taste.spicy",
                    "value": "不吃辣",
                    "confidence": 1.0,
                    "source": "user_explicit",
                },
            ],
            inventory_patches=[
                {"name": "鸡胸肉", "amount": "适量", "category": "肉类", "source": "user"},
                {"name": "番茄", "amount": "1个", "category": "蔬菜", "source": "user"},
                {"name": "鸡蛋", "amount": "2个", "category": "蛋类", "source": "user"},
            ],
        )

    return AgentOutput(
        intent="small_reply",
        ui_mode=_current_mode(context),
        speech="我先按当前厨房任务继续。",
        ui_patch={},
        tool_calls=[],
    )

