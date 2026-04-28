"""Initial mock Agent runtime for phase 3-5."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend import database
from backend.agent.prompts import render_agent_messages
from backend.agent.providers import MockAgentProvider, MockVisionProvider, ProviderError, get_agent_provider, get_vision_provider
from backend.agent.schemas import AgentOutput, ChatRequest
from backend.agent.voice_router import route_voice_text
from backend.config import get_settings
from backend.skills import inventory, memory, recipe, vision
from backend.terminal import state as terminal_state


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
    status: str = "success",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    return database.add_tool_event(
        terminal_id=terminal_id,
        event_type="agent_tool",
        name=name,
        input_json=input_json,
        output_json=output_json,
        status=status,
        db_path=db_path,
    )


def _provider_log(
    terminal_id: str,
    provider: str,
    model: Optional[str],
    status: str,
    latency_ms: Optional[int],
    error: Optional[str],
    db_path: Optional[str],
) -> None:
    settings = get_settings()
    if not settings.enable_provider_logs:
        return
    database.add_provider_log(
        provider=provider,
        model=model,
        status=status,
        latency_ms=latency_ms,
        error=error,
        terminal_id=terminal_id,
        db_path=db_path,
    )


def _provider_error_event(
    terminal_id: str,
    provider: str,
    model: Optional[str],
    error: str,
    latency_ms: Optional[int],
    db_path: Optional[str],
) -> Dict[str, Any]:
    return _record_event(
        terminal_id,
        "provider_error",
        input_json={"provider": provider, "model": model},
        output_json={
            "provider": provider,
            "model": model,
            "status": "fallback_to_mock",
            "latency_ms": latency_ms,
            "error": error[:500],
        },
        status="fallback",
        db_path=db_path,
    )


def detect_p0_command(text: str) -> Optional[str]:
    route = route_voice_text(text)
    if route.route == "local_control":
        return route.command
    return None


def _vision_speech(observation_dict: Dict[str, Any]) -> str:
    ingredients = observation_dict.get("ingredients") or []
    ingredient_map = {item.get("name"): item for item in ingredients if item.get("name")}
    tomato_amount = str((ingredient_map.get("番茄") or {}).get("amount") or "")
    chicken_amount = str((ingredient_map.get("鸡胸肉") or {}).get("amount") or "")
    if tomato_amount == "半个":
        return "我看到番茄只有半个，我会把这道菜改成一人份。"
    if chicken_amount == "少量":
        return "我看到鸡胸肉比较少，我会按实际食材更新库存和做法。"
    if ingredients:
        observed = "、".join(
            f"{item.get('name')}{item.get('amount') or ''}"
            for item in ingredients[:3]
            if item.get("name")
        )
        if observed:
            return f"我看到{observed}，已按识别结果更新库存。"
    return "我没有识别到明确食材，先保持当前菜谱。"


def _handle_start_vision(
    terminal_id: str,
    state: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Dict[str, Any]:
    speech = "好的，我来看看台面上的食材。请把食材放到镜头前。"
    next_state = dict(state)
    next_state["ui_mode"] = "vision"
    next_state["last_speech"] = speech
    next_state = database.save_state(terminal_id, next_state, db_path=db_path)
    output_json = {
        "model_called": False,
        "speech": speech,
        "voice_route": voice_route.to_dict(),
    }
    event = database.add_tool_event(
        terminal_id=terminal_id,
        event_type="local_control",
        name="start_vision",
        input_json={"intent": "start_vision", "text": voice_route.normalized_text},
        output_json=output_json,
        status="success",
        db_path=db_path,
    )
    return {
        "data": output_json,
        "state": next_state,
        "events": [event],
    }


def _memory_action_response(
    terminal_id: str,
    state: Dict[str, Any],
    event_name: str,
    speech: str,
    memory_action: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Dict[str, Any]:
    output_json = {
        "model_called": False,
        "speech": speech,
        "memory_action": memory_action,
        "voice_route": voice_route.to_dict(),
    }
    next_state = dict(state)
    next_state["last_speech"] = speech
    next_state = database.save_state(terminal_id, next_state, db_path=db_path)
    event = database.add_tool_event(
        terminal_id=terminal_id,
        event_type="local_control",
        name=event_name,
        input_json={"intent": voice_route.intent, "text": voice_route.normalized_text},
        output_json=output_json,
        status="success",
        db_path=db_path,
    )
    return {
        "data": output_json,
        "state": next_state,
        "events": [event],
    }


def _handle_memory_delete_request(
    terminal_id: str,
    state: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Dict[str, Any]:
    state = dict(state)
    state.pop("pending_action", None)
    candidates = memory.find_memory_candidates(terminal_id, voice_route.normalized_text, db_path=db_path)
    if not candidates:
        speech = "我没有找到相关的家庭记忆，先不做删除。"
        return _memory_action_response(
            terminal_id,
            state,
            "memory_delete_not_found",
            speech,
            {"type": "not_found", "memory_id": None, "summary": None},
            voice_route,
            db_path,
        )

    target = candidates[0]
    summary = memory.summarize_memory(target)
    next_state = dict(state)
    next_state["pending_action"] = {
        "type": "delete_memory",
        "memory_id": target["id"],
        "summary": summary,
        "created_at": database.utc_now(),
    }
    speech = f"确认删除“{summary}”这条家庭记忆吗？"
    return _memory_action_response(
        terminal_id,
        next_state,
        "memory_delete_pending",
        speech,
        {
            "type": "delete_pending",
            "memory_id": target["id"],
            "summary": summary,
        },
        voice_route,
        db_path,
    )


def _handle_memory_delete_confirm(
    terminal_id: str,
    state: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Dict[str, Any]:
    pending = state.get("pending_action") or {}
    if pending.get("type") != "delete_memory":
        speech = "当前没有需要确认的记忆操作。"
        return _memory_action_response(
            terminal_id,
            state,
            "memory_delete_not_found",
            speech,
            {"type": "not_found", "memory_id": None, "summary": None},
            voice_route,
            db_path,
        )

    memory_id = str(pending.get("memory_id") or "")
    summary = str(pending.get("summary") or "这条记忆")
    deleted = memory.delete_memory(terminal_id, memory_id, db_path=db_path) if memory_id else None
    next_state = dict(state)
    next_state.pop("pending_action", None)
    if not deleted:
        speech = "这条家庭记忆已经不存在了，我已清空待确认操作。"
        return _memory_action_response(
            terminal_id,
            next_state,
            "memory_delete_not_found",
            speech,
            {"type": "not_found", "memory_id": memory_id or None, "summary": summary},
            voice_route,
            db_path,
        )

    speech = "已删除这条家庭记忆。"
    return _memory_action_response(
        terminal_id,
        next_state,
        "memory_delete",
        speech,
        {"type": "deleted", "memory_id": memory_id, "summary": summary},
        voice_route,
        db_path,
    )


def _handle_memory_delete_cancel(
    terminal_id: str,
    state: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Dict[str, Any]:
    pending = state.get("pending_action") or {}
    if pending.get("type") != "delete_memory":
        speech = "当前没有需要取消的记忆操作。"
        return _memory_action_response(
            terminal_id,
            state,
            "memory_delete_not_found",
            speech,
            {"type": "not_found", "memory_id": None, "summary": None},
            voice_route,
            db_path,
        )
    next_state = dict(state)
    next_state.pop("pending_action", None)
    summary = str(pending.get("summary") or "这条记忆")
    speech = "好的，已保留这条记忆。"
    return _memory_action_response(
        terminal_id,
        next_state,
        "memory_delete_cancel",
        speech,
        {
            "type": "cancel",
            "memory_id": pending.get("memory_id"),
            "summary": summary,
        },
        voice_route,
        db_path,
    )


def _handle_memory_action(
    terminal_id: str,
    state: Dict[str, Any],
    voice_route: Any,
    db_path: Optional[str],
) -> Optional[Dict[str, Any]]:
    if voice_route.intent == "memory_delete_request":
        return _handle_memory_delete_request(terminal_id, state, voice_route, db_path)
    if voice_route.intent == "memory_delete_confirm":
        return _handle_memory_delete_confirm(terminal_id, state, voice_route, db_path)
    if voice_route.intent == "memory_delete_cancel":
        return _handle_memory_delete_cancel(terminal_id, state, voice_route, db_path)
    return None


def _clear_stale_pending_delete(
    terminal_id: str,
    state: Dict[str, Any],
    db_path: Optional[str],
) -> Dict[str, Any]:
    pending = state.get("pending_action") or {}
    if pending.get("type") != "delete_memory":
        return state
    next_state = dict(state)
    next_state.pop("pending_action", None)
    return database.save_state(terminal_id, next_state, db_path=db_path)


def handle_chat(
    request: ChatRequest,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    resolved_db_path = db_path or settings.db_path
    terminal_id = request.terminal_id or settings.default_terminal_id
    state = terminal_state.get_state(terminal_id, db_path=resolved_db_path)
    voice_route = route_voice_text(request.text, state)
    if voice_route.route == "memory_action":
        result = _handle_memory_action(terminal_id, state, voice_route, resolved_db_path)
        if result is not None:
            return result
    state = _clear_stale_pending_delete(terminal_id, state, resolved_db_path)
    if voice_route.route == "local_control" and voice_route.command:
        result = terminal_state.apply_control(voice_route.command, terminal_id, db_path=resolved_db_path)
        result["data"]["voice_route"] = voice_route.to_dict()
        return result
    if voice_route.intent == "start_vision":
        return _handle_start_vision(terminal_id, state, voice_route, resolved_db_path)

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
        "recipe_documents": database.list_recipe_documents(terminal_id, db_path=resolved_db_path),
        "recent_messages": database.list_recent_conversations(terminal_id, db_path=resolved_db_path),
    }
    events: List[Dict[str, Any]] = []
    provider = get_agent_provider(settings)
    messages = render_agent_messages(request.text, context)
    provider_error: Optional[str] = None
    start_ms = time.perf_counter()
    try:
        agent_output = provider.chat_json(request.text, context, messages=messages)
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        if not isinstance(provider, MockAgentProvider):
            _provider_log(terminal_id, provider.name, provider.model, "success", latency_ms, None, resolved_db_path)
            events.append(
                _record_event(
                    terminal_id,
                    "provider_call",
                    input_json={"provider": provider.name, "model": provider.model},
                    output_json={"status": "success", "latency_ms": latency_ms},
                    db_path=resolved_db_path,
                )
            )
    except ProviderError as exc:
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        provider_error = str(exc)
        _provider_log(terminal_id, exc.provider, exc.model, "error", latency_ms, provider_error, resolved_db_path)
        events.append(
            _provider_error_event(
                terminal_id,
                exc.provider,
                exc.model,
                provider_error,
                latency_ms,
                resolved_db_path,
            )
        )
        agent_output = MockAgentProvider().chat_json(request.text, context)

    tool_names = _tool_names(agent_output)

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
            "provider": {
                "mode": settings.demo_mode,
                "name": provider.name,
                "model": provider.model,
                "fallback_used": provider_error is not None,
                "error": provider_error,
            },
        },
        "state": next_state,
        "events": events,
    }


def handle_vision(
    terminal_id: str,
    purpose: str = "ingredients",
    image_bytes: Optional[bytes] = None,
    content_type: str = "image/jpeg",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    resolved_db_path = db_path or settings.db_path
    state = terminal_state.get_state(terminal_id, db_path=resolved_db_path)
    provider = get_vision_provider(settings)
    provider_error: Optional[str] = None
    events: List[Dict[str, Any]] = []
    start_ms = time.perf_counter()
    try:
        observation = provider.observe_ingredients(
            image_bytes=image_bytes,
            content_type=content_type,
            purpose=purpose,
        )
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        if not isinstance(provider, MockVisionProvider):
            _provider_log(terminal_id, provider.name, provider.model, "success", latency_ms, None, resolved_db_path)
            events.append(
                _record_event(
                    terminal_id,
                    "provider_call",
                    input_json={"provider": provider.name, "model": provider.model, "purpose": purpose},
                    output_json={"status": "success", "latency_ms": latency_ms},
                    db_path=resolved_db_path,
                )
            )
    except ProviderError as exc:
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        provider_error = str(exc)
        _provider_log(terminal_id, exc.provider, exc.model, "error", latency_ms, provider_error, resolved_db_path)
        events.append(
            _record_event(
                terminal_id,
                "vision_provider_fallback",
                input_json={"provider": exc.provider, "model": exc.model, "purpose": purpose},
                output_json={
                    "status": "fallback_to_mock",
                    "latency_ms": latency_ms,
                    "error": provider_error[:500],
                },
                status="fallback",
                db_path=resolved_db_path,
            )
        )
        observation = vision.mock_observe_ingredients()
    observation_dict = _model_to_dict(observation)
    events.append(
        _record_event(
            terminal_id,
            "vision_observe",
            input_json={"purpose": purpose},
            output_json={
                "observation": observation_dict,
                "provider": {
                    "mode": settings.demo_mode,
                    "name": provider.name,
                    "model": provider.model,
                    "fallback_used": provider_error is not None,
                    "error": provider_error,
                },
            },
            db_path=resolved_db_path,
        )
    )
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
    speech = _vision_speech(observation_dict)
    next_state["last_speech"] = speech
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
    database.add_conversation(
        terminal_id,
        "assistant",
        speech,
        metadata_json={"intent": "vision_observe"},
        db_path=resolved_db_path,
    )
    return {
        "data": {
            "observation": observation_dict,
            "speech": speech,
            "provider": {
                "mode": settings.demo_mode,
                "name": provider.name,
                "model": provider.model,
                "fallback_used": provider_error is not None,
                "error": provider_error,
            },
        },
        "state": next_state,
        "events": events,
    }
