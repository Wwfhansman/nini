"""Initial mock Agent runtime for phase 3-5."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend import database
from backend.agent.providers import get_model_provider
from backend.agent.schemas import AgentOutput, ChatRequest, VisionObservation
from backend.config import get_settings
from backend.skills import inventory, memory, recipe, vision
from backend.terminal import state as terminal_state


P0_COMMANDS = {
    "开始": "start",
    "开始做": "start",
    "下一步": "next_step",
    "上一步": "previous_step",
    "暂停": "pause",
    "继续": "resume",
    "完成": "finish",
}
P0_TRAILING_PUNCTUATION = "。！？!?.,，；;：:、 "


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _tool_names(agent_output: AgentOutput) -> List[str]:
    return [str(call.get("name")) for call in agent_output.tool_calls if call.get("name")]


def _record_event(
    terminal_id: str,
    name: str,
    input_json: Optional[Dict[str, Any]] = None,
    output_json: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    return database.add_tool_event(
        terminal_id=terminal_id,
        event_type="agent_tool",
        name=name,
        input_json=input_json,
        output_json=output_json,
        status="success",
        db_path=db_path,
    )


def detect_p0_command(text: str) -> Optional[str]:
    normalized = text.strip().strip(P0_TRAILING_PUNCTUATION)
    return P0_COMMANDS.get(normalized)


def handle_chat(
    request: ChatRequest,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    resolved_db_path = db_path or settings.db_path
    terminal_id = request.terminal_id or settings.default_terminal_id
    command = detect_p0_command(request.text)
    if command:
        return terminal_state.apply_control(command, terminal_id, db_path=resolved_db_path)

    state = terminal_state.get_state(terminal_id, db_path=resolved_db_path)
    database.add_conversation(
        terminal_id,
        "user",
        request.text,
        metadata_json={"source": request.source},
        db_path=resolved_db_path,
    )
    relevant_memories = memory.search_memories(
        terminal_id,
        query=request.text,
        context={"dish_name": state.get("dish_name")},
        db_path=resolved_db_path,
    )
    context = {
        "state": state,
        "memories": relevant_memories,
        "inventory": inventory.inventory_summary(terminal_id, db_path=resolved_db_path),
        "recent_messages": database.list_recent_conversations(terminal_id, db_path=resolved_db_path),
    }
    provider = get_model_provider(settings.demo_mode)
    agent_output = provider.chat_json(request.text, context)
    tool_names = _tool_names(agent_output)
    events: List[Dict[str, Any]] = []

    written_memories = []
    if agent_output.memory_writes:
        written_memories = memory.write_memories(
            terminal_id,
            agent_output.memory_writes,
            db_path=resolved_db_path,
        )
        events.append(
            _record_event(
                terminal_id,
                "memory_write",
                input_json={"count": len(agent_output.memory_writes)},
                output_json={"memories": written_memories},
                db_path=resolved_db_path,
            )
        )

    updated_inventory = []
    if agent_output.inventory_patches:
        updated_inventory = inventory.apply_inventory_patches(
            terminal_id,
            agent_output.inventory_patches,
            db_path=resolved_db_path,
        )
        events.append(
            _record_event(
                terminal_id,
                "inventory_update",
                input_json={"count": len(agent_output.inventory_patches)},
                output_json={"items": updated_inventory},
                db_path=resolved_db_path,
            )
        )

    next_state = dict(state)
    if agent_output.intent == "plan_recipe" or "recipe_plan" in tool_names:
        planned_recipe = recipe.plan_recipe(context)
        next_state.update(
            {
                "ui_mode": "planning",
                "dish_name": planned_recipe["dish_name"],
                "recipe": planned_recipe,
                "current_step_index": 0,
                "timer_status": "idle",
                "timer_remaining_seconds": 0,
                "active_adjustments": planned_recipe.get("adjustments", []),
            }
        )
        events.append(
            _record_event(
                terminal_id,
                "recipe_plan",
                input_json={"intent": agent_output.intent},
                output_json={"dish_name": planned_recipe["dish_name"]},
                db_path=resolved_db_path,
            )
        )

    adjusted_for_memory = False
    for item in written_memories:
        if item.get("key") == "taste.sour":
            next_state = recipe.adjust_recipe_for_memory(next_state, item)
            adjusted_for_memory = True
    if adjusted_for_memory or agent_output.recipe_adjustments:
        if state.get("ui_mode") == "cooking":
            next_state["ui_mode"] = "cooking"
        else:
            next_state["ui_mode"] = agent_output.ui_mode
        events.append(
            _record_event(
                terminal_id,
                "recipe_adjust",
                input_json={"reason": "memory"},
                output_json={"adjustments": next_state.get("active_adjustments", [])},
                db_path=resolved_db_path,
            )
        )
    elif agent_output.intent != "plan_recipe":
        next_state["ui_mode"] = state.get("ui_mode", agent_output.ui_mode)

    next_state["last_speech"] = agent_output.speech
    next_state = database.save_state(terminal_id, next_state, db_path=resolved_db_path)
    database.add_conversation(
        terminal_id,
        "assistant",
        agent_output.speech,
        metadata_json={"intent": agent_output.intent},
        db_path=resolved_db_path,
    )
    return {
        "data": {
            "speech": agent_output.speech,
            "intent": agent_output.intent,
            "ui_patch": agent_output.ui_patch,
        },
        "state": next_state,
        "events": events,
    }


def handle_vision(
    terminal_id: str,
    purpose: str = "ingredients",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    resolved_db_path = db_path or settings.db_path
    state = terminal_state.get_state(terminal_id, db_path=resolved_db_path)
    observation = vision.mock_observe_ingredients()
    observation_dict = _model_to_dict(observation)
    events = [
        _record_event(
            terminal_id,
            "vision_observe",
            input_json={"purpose": purpose},
            output_json={"observation": observation_dict},
            db_path=resolved_db_path,
        )
    ]
    patches = [
        {
            "name": ingredient.name,
            "amount": ingredient.amount,
            "category": "食材",
            "source": "vision",
        }
        for ingredient in observation.ingredients
    ]
    updated_inventory = inventory.apply_inventory_patches(terminal_id, patches, db_path=resolved_db_path)
    events.append(
        _record_event(
            terminal_id,
            "inventory_update",
            input_json={"source": "vision", "count": len(patches)},
            output_json={"items": updated_inventory},
            db_path=resolved_db_path,
        )
    )
    next_state = recipe.adjust_recipe_for_vision(state, observation)
    next_state = database.save_state(terminal_id, next_state, db_path=resolved_db_path)
    events.append(
        _record_event(
            terminal_id,
            "recipe_adjust",
            input_json={"reason": "vision"},
            output_json={"adjustments": next_state.get("active_adjustments", [])},
            db_path=resolved_db_path,
        )
    )
    speech = "我看到番茄只有半个，我会把这道菜改成一人份。"
    database.add_conversation(
        terminal_id,
        "assistant",
        speech,
        metadata_json={"intent": "vision_observe"},
        db_path=resolved_db_path,
    )
    return {
        "data": {"observation": observation_dict, "speech": speech},
        "state": next_state,
        "events": events,
    }
