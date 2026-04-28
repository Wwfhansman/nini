"""Local terminal state machine for deterministic P0 controls."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend import database
from backend.agent.schemas import CookingStep, RecipePlan, TerminalStateSnapshot


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _default_recipe() -> Dict[str, Any]:
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
            instruction="加入番茄轻炒，再倒入鸡蛋，翻炒到鸡蛋凝固。",
            ingredients=["番茄", "鸡蛋"],
            heat="中小火",
            duration_seconds=150,
        ),
        CookingStep(
            index=5,
            title="调味出锅",
            instruction="用少量盐调味，不放辣椒，确认熟透后出锅。",
            ingredients=["盐"],
            heat="关火",
            duration_seconds=60,
        ),
    ]
    recipe = RecipePlan(
        dish_name="低脂不辣番茄鸡胸肉滑蛋",
        servings="1-2人份",
        estimated_minutes=18,
        reasoning_summary="符合减脂目标，不放辣，并使用鸡胸肉、番茄和鸡蛋完成一顿饭主菜。",
        ingredients=["鸡胸肉", "番茄", "鸡蛋", "盐", "淀粉", "少量油"],
        steps=steps,
        adjustments=[],
    )
    return _model_to_dict(recipe)


def default_state(terminal_id: str) -> Dict[str, Any]:
    snapshot = TerminalStateSnapshot(
        terminal_id=terminal_id,
        ui_mode="planning",
        dish_name="低脂不辣番茄鸡胸肉滑蛋",
        recipe=_default_recipe(),
        current_step_index=0,
        timer_status="idle",
        timer_remaining_seconds=0,
        active_adjustments=[],
        last_speech="今晚可以先从这道低脂不辣番茄鸡胸肉滑蛋开始。",
    )
    return _model_to_dict(snapshot)


def _recipe_steps(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    recipe = state.get("recipe") or _default_recipe()
    state["recipe"] = recipe
    state["dish_name"] = state.get("dish_name") or recipe["dish_name"]
    return recipe.get("steps", [])


def _current_step_duration(state: Dict[str, Any]) -> int:
    steps = _recipe_steps(state)
    if not steps:
        return 0
    index = min(max(int(state.get("current_step_index", 0)), 0), len(steps) - 1)
    state["current_step_index"] = index
    return int(steps[index].get("duration_seconds", 0) or 0)


def get_state(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = database.get_state(terminal_id, db_path=db_path)
    if state is None:
        state = database.save_state(terminal_id, default_state(terminal_id), db_path=db_path)
    if not state.get("recipe"):
        state["recipe"] = _default_recipe()
        state = database.save_state(terminal_id, state, db_path=db_path)
    return state


def reset_state(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    database.reset_demo_data(terminal_id, db_path=db_path)
    return database.save_state(terminal_id, default_state(terminal_id), db_path=db_path)


def start_cooking(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    state["ui_mode"] = "cooking"
    state["current_step_index"] = min(max(int(state.get("current_step_index", 0)), 0), len(_recipe_steps(state)) - 1)
    state["timer_status"] = "running"
    state["timer_remaining_seconds"] = _current_step_duration(state)
    state["last_speech"] = "开始做这道低脂不辣番茄鸡胸肉滑蛋。"
    return database.save_state(terminal_id, state, db_path=db_path)


def next_step(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    steps = _recipe_steps(state)
    current = int(state.get("current_step_index", 0))
    state["current_step_index"] = min(current + 1, max(len(steps) - 1, 0))
    state["ui_mode"] = "cooking"
    state["timer_status"] = "running"
    state["timer_remaining_seconds"] = _current_step_duration(state)
    state["last_speech"] = "进入下一步。"
    return database.save_state(terminal_id, state, db_path=db_path)


def previous_step(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    current = int(state.get("current_step_index", 0))
    state["current_step_index"] = max(current - 1, 0)
    state["ui_mode"] = "cooking"
    state["timer_status"] = "running"
    state["timer_remaining_seconds"] = _current_step_duration(state)
    state["last_speech"] = "回到上一步。"
    return database.save_state(terminal_id, state, db_path=db_path)


def pause_timer(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    if state.get("ui_mode") == "cooking" and state.get("timer_status") == "running":
        state["timer_status"] = "paused"
        state["last_speech"] = "已暂停。"
    else:
        state["last_speech"] = "当前没有正在运行的烹饪计时。"
    return database.save_state(terminal_id, state, db_path=db_path)


def resume_timer(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    if state.get("ui_mode") == "cooking" and state.get("timer_status") == "paused":
        state["timer_status"] = "running"
        if int(state.get("timer_remaining_seconds", 0) or 0) <= 0:
            state["timer_remaining_seconds"] = _current_step_duration(state)
        state["last_speech"] = "继续。"
    else:
        state["last_speech"] = "当前没有已暂停的烹饪计时。"
    return database.save_state(terminal_id, state, db_path=db_path)


def repeat_current_step(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    return get_state(terminal_id, db_path=db_path)


def current_step_speech(state: Dict[str, Any]) -> str:
    recipe = state.get("recipe") or {}
    steps = recipe.get("steps") or []
    if not steps:
        return "当前还没有烹饪步骤，请先规划一道菜。"
    index = min(max(int(state.get("current_step_index", 0)), 0), len(steps) - 1)
    step = steps[index]
    title = step.get("title") or f"第{index + 1}步"
    instruction = step.get("instruction") or "这一步暂时没有详细说明。"
    return f"当前步骤：{title}。{instruction}"


def finish_cooking(terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    state = get_state(terminal_id, db_path=db_path)
    state["ui_mode"] = "review"
    state["timer_status"] = "finished"
    state["timer_remaining_seconds"] = 0
    state["last_speech"] = "已完成，进入复盘。"
    return database.save_state(terminal_id, state, db_path=db_path)


def apply_control(command: str, terminal_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    handlers = {
        "start": start_cooking,
        "next_step": next_step,
        "previous_step": previous_step,
        "pause": pause_timer,
        "resume": resume_timer,
        "finish": finish_cooking,
        "reset": reset_state,
        "repeat_current_step": repeat_current_step,
    }
    if command not in handlers:
        raise ValueError(f"Unsupported control command: {command}")

    state = handlers[command](terminal_id, db_path=db_path)
    if state.get("pending_action"):
        state = dict(state)
        state.pop("pending_action", None)
        state = database.save_state(terminal_id, state, db_path=db_path)
    speech = current_step_speech(state) if command == "repeat_current_step" else state.get("last_speech", "")
    output_json = {
        "model_called": False,
        "speech": speech,
    }
    event = database.add_tool_event(
        terminal_id=terminal_id,
        event_type="local_control",
        name=command,
        input_json={"command": command},
        output_json=output_json,
        status="success",
        db_path=db_path,
    )
    return {
        "data": output_json,
        "state": state,
        "events": [event],
    }
