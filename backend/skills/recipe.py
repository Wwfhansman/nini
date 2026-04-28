"""Recipe skill with fixed demo catalog and deterministic adjustments."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from backend.agent.schemas import CookingStep, RecipePlan, VisionObservation


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def base_recipe_plan() -> Dict[str, Any]:
    steps = [
        CookingStep(
            index=0,
            title="鸡胸肉切薄片并轻腌",
            instruction="把鸡胸肉切成薄片，加入少量盐和淀粉抓匀。",
            ingredients=["鸡胸肉", "盐", "淀粉"],
            heat="暂不加热",
            duration_seconds=180,
            tips=["薄片更容易熟，也更适合低脂快手做法。"],
        ),
        CookingStep(
            index=1,
            title="鸡蛋打散",
            instruction="把鸡蛋打散，保留滑嫩口感，不额外加糖。",
            ingredients=["鸡蛋"],
            heat="暂不加热",
            duration_seconds=60,
            tips=["鸡蛋比例略高，可以中和番茄酸味。"],
        ),
        CookingStep(
            index=2,
            title="番茄切小块",
            instruction="番茄切小块，后续只轻炒出汁，避免酸味过重。",
            ingredients=["番茄"],
            heat="暂不加热",
            duration_seconds=90,
        ),
        CookingStep(
            index=3,
            title="滑炒鸡胸肉",
            instruction="热锅少油，放入鸡胸肉快速滑炒到变色。",
            ingredients=["鸡胸肉", "少量油"],
            heat="中火",
            duration_seconds=120,
        ),
        CookingStep(
            index=4,
            title="加入番茄和鸡蛋",
            instruction="加入番茄轻炒，再倒入鸡蛋，翻炒到鸡蛋凝固。不放辣椒，不额外加糖。",
            ingredients=["番茄", "鸡蛋"],
            heat="中小火",
            duration_seconds=150,
        ),
        CookingStep(
            index=5,
            title="调味出锅",
            instruction="用少量盐调味，不放辣椒，不加醋，确认熟透后出锅。",
            ingredients=["盐"],
            heat="关火",
            duration_seconds=60,
        ),
    ]
    recipe = RecipePlan(
        dish_name="番茄鸡胸肉滑蛋",
        servings="1-2人份",
        estimated_minutes=18,
        reasoning_summary="使用鸡胸肉、番茄和鸡蛋完成一顿饭主菜。",
        ingredients=["鸡胸肉", "番茄", "鸡蛋", "盐", "淀粉", "少量油"],
        steps=steps,
        adjustments=[],
    )
    return _model_to_dict(recipe)


def _value_text(item: Dict[str, Any]) -> str:
    value = item.get("value_json")
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or value)
    return str(value or "")


def _context_text(context: Optional[Dict[str, Any]]) -> str:
    context = context or {}
    parts: List[str] = []
    parts.append(str(context.get("request_text") or ""))
    for item in context.get("memories") or []:
        parts.extend([str(item.get("subject") or ""), str(item.get("key") or ""), _value_text(item)])
    for item in context.get("inventory") or []:
        parts.extend([str(item.get("name") or ""), str(item.get("amount") or "")])
    for item in context.get("recipe_documents") or []:
        parts.extend([str(item.get("title") or ""), str(item.get("content") or "")])
    return " ".join(parts)


def _inventory_map(context: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("name")): item
        for item in (context or {}).get("inventory", [])
        if item.get("name")
    }


def _recipe_documents_match(context: Optional[Dict[str, Any]]) -> bool:
    for item in (context or {}).get("recipe_documents") or []:
        text = f"{item.get('title') or ''} {item.get('content') or ''}"
        if "妈妈版番茄炒蛋" in text or ("家庭" in text and "番茄" in text):
            return True
    return False


def plan_recipe(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    recipe = base_recipe_plan()
    text = _context_text(context)
    inventory = _inventory_map(context)
    reasons = []
    name_prefixes: List[str] = []

    if any(token in text for token in ["减脂", "低脂"]):
        name_prefixes.append("低脂")
        _append_unique(recipe["adjustments"], "少油/低脂")
        reasons.append("命中用户减脂或低脂目标，采用少油做法")
    if any(token in text for token in ["妈妈不吃辣", "不吃辣", "不放辣", "diet.spicy", "taste.spicy"]):
        name_prefixes.append("不辣")
        _append_unique(recipe["adjustments"], "不放辣")
        reasons.append("照顾妈妈不吃辣，菜谱不使用辣椒")
    if any(token in text for token in ["不喜欢太酸", "太酸", "taste.sour"]):
        _append_unique(recipe["adjustments"], "降低酸度")
        _append_unique(recipe["adjustments"], "增加鸡蛋比例")
        reasons.append("命中用户不喜欢太酸，减少番茄酸度")
        for step in recipe.get("steps", []):
            if step["title"] == "加入番茄和鸡蛋":
                step["duration_seconds"] = min(int(step.get("duration_seconds", 150)), 90)
                step["instruction"] = "番茄减少翻炒时间，再倒入鸡蛋，用鸡蛋比例中和酸味，不额外加醋。"

    if _recipe_documents_match(context):
        _append_unique(recipe["adjustments"], "参考家庭菜谱")
        reasons.append("参考已导入的家庭菜谱做法")

    if inventory:
        required = ["鸡胸肉", "番茄", "鸡蛋"]
        missing = [name for name in required if name not in inventory]
        if missing:
            recipe["ingredients"].extend([f"待确认：{name}" for name in missing])
            reasons.append(f"{'、'.join(missing)}库存未确认，建议烹饪前补充或替换")
        tomato_amount = str(inventory.get("番茄", {}).get("amount") or "")
        chicken_amount = str(inventory.get("鸡胸肉", {}).get("amount") or "")
        if "半个" in tomato_amount or "少量" in chicken_amount:
            recipe["servings"] = "1人份"
            _append_unique(recipe["adjustments"], "按现有食材减量")
            _append_unique(recipe["adjustments"], "降低酸度")
            reasons.append("根据现有食材数量改为一人份")

    recipe["dish_name"] = "".join(name_prefixes) + recipe["dish_name"]
    if reasons:
        recipe["reasoning_summary"] = "；".join(reasons) + "。"
    return recipe


def ensure_recipe(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("recipe"):
        state["recipe"] = base_recipe_plan()
    state["dish_name"] = state.get("dish_name") or state["recipe"]["dish_name"]
    return state["recipe"]


def _append_unique(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def adjust_recipe_for_vision(state: Dict[str, Any], observation: VisionObservation | Dict[str, Any]) -> Dict[str, Any]:
    next_state = deepcopy(state)
    recipe = ensure_recipe(next_state)
    obs = _model_to_dict(observation)
    ingredients = {item["name"]: item for item in obs.get("ingredients", [])}

    if ingredients.get("番茄", {}).get("amount") == "半个":
        recipe["servings"] = "1人份"
        _append_unique(recipe["adjustments"], "番茄只有半个，改为一人份")
        _append_unique(recipe["adjustments"], "降低酸度")
        for step in recipe.get("steps", []):
            if "番茄" in step.get("ingredients", []):
                step["changed_by_vision"] = True
                if step["title"] == "加入番茄和鸡蛋":
                    step["duration_seconds"] = min(int(step.get("duration_seconds", 150)), 90)
                    step["instruction"] = "番茄只轻炒出汁，再倒入鸡蛋，减少酸味并保证一人份口感。"
    if ingredients.get("鸡胸肉", {}).get("amount") == "少量":
        _append_unique(recipe["adjustments"], "鸡胸肉切薄片，保证熟得快")
    next_state["recipe"] = recipe
    next_state["dish_name"] = recipe["dish_name"]
    next_state["ui_mode"] = "vision"
    next_state["active_adjustments"] = recipe["adjustments"]
    next_state["last_speech"] = "我看到番茄只有半个，我会把这道菜改成一人份，并降低酸度。"
    return next_state


def adjust_recipe_for_memory(state: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
    next_state = deepcopy(state)
    recipe = ensure_recipe(next_state)
    if memory.get("key") == "taste.sour":
        _append_unique(recipe["adjustments"], "用户不喜欢太酸")
        _append_unique(recipe["adjustments"], "增加鸡蛋比例")
        _append_unique(recipe["adjustments"], "不额外加醋")
        for step in recipe.get("steps", []):
            if "番茄" in step.get("ingredients", []):
                step["changed_by_memory"] = True
            if step["title"] == "加入番茄和鸡蛋":
                step["duration_seconds"] = min(int(step.get("duration_seconds", 150)), 45)
                step["instruction"] = "番茄快速轻炒约 45 秒，增加鸡蛋比例来中和酸味，不额外加醋。"
            if step["title"] == "调味出锅":
                step["instruction"] = "用少量盐调味，不放辣椒，不加醋，确认熟透后出锅。"
    next_state["recipe"] = recipe
    next_state["dish_name"] = recipe["dish_name"]
    next_state["active_adjustments"] = recipe["adjustments"]
    next_state["last_speech"] = "好，我会把这道菜调得不那么酸。"
    return next_state


def build_review(
    state: Dict[str, Any],
    memories: List[Dict[str, Any]],
    inventory_changes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    dish_name = state.get("dish_name") or "本次菜品"
    next_time = ["番茄类菜品默认降低酸度", "继续保持不辣", "优先少油做法"]
    return {
        "dish_name": dish_name,
        "summary": f"本次完成{dish_name}。",
        "used_ingredients": [item.get("name") for item in inventory_changes],
        "inventory_changes": inventory_changes,
        "memory_count": len(memories),
        "next_time": next_time,
    }
