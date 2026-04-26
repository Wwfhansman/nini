"""FastAPI application for the phase 0-2 backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query

from backend import database
from backend.agent.schemas import ApiResponse, ControlRequest
from backend.config import get_settings
from backend.terminal import state as terminal_state


def _init_runtime() -> None:
    settings = get_settings()
    database.init_db(settings.db_path)
    terminal_state.get_state(settings.default_terminal_id, db_path=settings.db_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_runtime()
    yield


app = FastAPI(title="Nini Kitchen Agent Backend", lifespan=lifespan)


def _public_event(event: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(event)
    public["input"] = public.pop("input_json", None)
    public["output"] = public.pop("output_json", None)
    return public


def _public_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_public_event(event) for event in events]


@app.get("/health")
def health() -> dict:
    _init_runtime()
    settings = get_settings()
    return {
        "ok": True,
        "app_env": settings.app_env,
        "demo_mode": settings.demo_mode,
    }


@app.get("/api/state", response_model=ApiResponse)
def get_api_state(terminal_id: Optional[str] = Query(default=None)) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_terminal_id = terminal_id or settings.default_terminal_id
    state = terminal_state.get_state(resolved_terminal_id, db_path=settings.db_path)
    events = _public_events(database.list_tool_events(resolved_terminal_id, db_path=settings.db_path))
    data = {
        "terminal_id": resolved_terminal_id,
        "state": state,
        "memories": database.list_memories(resolved_terminal_id, db_path=settings.db_path),
        "inventory": database.list_inventory_items(resolved_terminal_id, db_path=settings.db_path),
        "tool_events": events,
    }
    return ApiResponse(ok=True, data=data, state=state, events=events, error=None)


@app.post("/api/control", response_model=ApiResponse)
def post_control(request: ControlRequest) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_terminal_id = request.terminal_id or settings.default_terminal_id
    result = terminal_state.apply_control(
        request.command,
        resolved_terminal_id,
        db_path=settings.db_path,
    )
    events = _public_events(result["events"])
    return ApiResponse(
        ok=True,
        data=result["data"],
        state=result["state"],
        events=events,
        error=None,
    )
