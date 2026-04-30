"""Deterministic UI patch builders for fixed frontend templates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agent.schemas import sanitize_ui_patch


def _value_text(item: Dict[str, Any]) -> str:
    value = item.get("value_json")
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or "")
    return str(value or "")


def _ingredient_names(items: List[Dict[str, Any]], limit: int = 3) -> str:
    names = [str(item.get("name") or "") for item in items if item.get("name")]
    return "、".join(names[:limit])


def _merge_patch(fallback: Dict[str, Any], preferred: Any = None) -> Dict[str, Any]:
    preferred_patch = sanitize_ui_patch(preferred)
    if not preferred_patch:
        return sanitize_ui_patch(fallback)
    merged = dict(fallback)
    for key in ("title", "subtitle", "attention"):
        if preferred_patch.get(key):
            merged[key] = preferred_patch[key]
    if preferred_patch.get("cards"):
        merged["cards"] = preferred_patch["cards"]
    if preferred_patch.get("suggested_phrases"):
        merged["suggested_phrases"] = preferred_patch["suggested_phrases"]
    return sanitize_ui_patch(merged)


def build_planning_ui_patch(
    recipe: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    preferred: Any = None,
) -> Dict[str, Any]:
    context = context or {}
    memories = context.get("memories") or []
    inventory = context.get("inventory") or []
    documents = context.get("recipe_documents") or []
    adjustments = recipe.get("adjustments") or []

    cards: List[Dict[str, str]] = []
    text = " ".join(
        [str(context.get("request_text") or ""), recipe.get("reasoning_summary") or ""]
        + [_value_text(item) for item in memories]
    )
    if "减脂" in text or "低脂" in text or "少油" in text:
        cards.append({"label": "健康目标", "value": "少油低脂", "tone": "health"})
    if "不吃辣" in text or "不放辣" in text or "diet.spicy" in text:
        cards.append({"label": "饮食限制", "value": "妈妈不吃辣", "tone": "restrict"})
    inventory_names = _ingredient_names(inventory)
    if inventory_names:
        cards.append({"label": "当前库存", "value": inventory_names, "tone": "success"})
    if documents:
        cards.append({"label": "家庭菜谱", "value": str(documents[0].get("title") or "已命中"), "tone": "preference"})
    if adjustments:
        cards.append({"label": "方案调整", "value": "、".join(adjustments[:2]), "tone": "warning"})

    attention = ""
    if any("番茄只有半个" in item for item in adjustments):
        attention = "番茄只有半个，已调整为一人份"
    elif adjustments:
        attention = str(adjustments[0])

    fallback = {
        "title": recipe.get("dish_name") or "今晚推荐方案",
        "subtitle": recipe.get("reasoning_summary") or "根据家庭记忆、健康目标和当前库存生成。",
        "attention": attention,
        "cards": cards,
        "suggested_phrases": ["就做这个", "看看食材", "换一道"],
    }
    return _merge_patch(fallback, preferred)


def build_vision_prompt_ui_patch(preferred: Any = None) -> Dict[str, Any]:
    fallback = {
        "title": "我来看看台面上的食材",
        "subtitle": "把食材放到镜头前，妮妮会按识别结果调整方案。",
        "suggested_phrases": ["重新看一下", "确认这些食材", "按这些调整"],
    }
    return _merge_patch(fallback, preferred)


def build_vision_ui_patch(
    observation: Dict[str, Any],
    adjustments: Optional[List[str]] = None,
    preferred: Any = None,
) -> Dict[str, Any]:
    adjustments = adjustments or []
    ingredients = observation.get("ingredients") or []
    cards = [
        {
            "label": str(item.get("name") or "食材"),
            "value": str(item.get("amount") or "已识别"),
            "tone": "warning" if any(token in str(item.get("amount") or "") for token in ["半", "少"]) else "success",
        }
        for item in ingredients[:4]
    ]
    if adjustments:
        cards.append({"label": "调整影响", "value": "、".join(adjustments[:2]), "tone": "warning"})
    attention = ""
    if any(item.get("name") == "番茄" and item.get("amount") == "半个" for item in ingredients):
        attention = "番茄只有半个，已调整为一人份"
    elif adjustments:
        attention = str(adjustments[0])
    fallback = {
        "title": "我看到了这些食材",
        "subtitle": "已根据台面画面更新库存和菜谱。",
        "attention": attention,
        "cards": cards,
        "suggested_phrases": ["按这些调整", "重新看一下", "开始做"],
    }
    return _merge_patch(fallback, preferred)


def build_cooking_ui_patch(state: Dict[str, Any], preferred: Any = None) -> Dict[str, Any]:
    recipe = state.get("recipe") or {}
    steps = recipe.get("steps") or []
    index = min(max(int(state.get("current_step_index", 0) or 0), 0), max(len(steps) - 1, 0)) if steps else 0
    step = steps[index] if steps else {}
    fallback = {
        "title": step.get("title") or recipe.get("dish_name") or "当前步骤",
        "subtitle": step.get("instruction") or state.get("last_speech") or "",
        "attention": (state.get("active_adjustments") or [""])[0],
        "suggested_phrases": ["下一步", "等一下", "这一步再说一遍", "做完了"],
    }
    return _merge_patch(fallback, preferred)


def build_review_ui_patch(
    state: Dict[str, Any],
    memories: Optional[List[Dict[str, Any]]] = None,
    preferred: Any = None,
) -> Dict[str, Any]:
    recipe = state.get("recipe") or {}
    review = state.get("review") or {}
    inventory_changes = review.get("inventory_changes") or []
    memories = memories or []
    cards = [
        {
            "label": "预计用时",
            "value": f"{recipe.get('estimated_minutes', '—')} 分钟",
            "tone": "neutral",
        },
        {
            "label": "食材消耗",
            "value": f"{len(inventory_changes)} 项",
            "tone": "success" if inventory_changes else "neutral",
        },
        {
            "label": "家庭记忆",
            "value": f"{len(memories)} 条",
            "tone": "preference" if memories else "neutral",
        },
    ]
    next_time = review.get("next_time") or []
    if next_time:
        cards.append({"label": "下次建议", "value": str(next_time[0]), "tone": "warning"})

    attention = ""
    if inventory_changes:
        attention = f"本次已记录 {len(inventory_changes)} 项食材消耗"
    elif memories:
        attention = f"当前保留 {len(memories)} 条家庭记忆"

    fallback = {
        "title": "本次烹饪复盘",
        "subtitle": review.get("summary") or f"已完成{state.get('dish_name') or '本次烹饪'}。",
        "attention": attention,
        "cards": cards,
        "suggested_phrases": ["再做一道", "导出家庭记忆", "下次少放盐"],
    }
    return _merge_patch(fallback, preferred)
