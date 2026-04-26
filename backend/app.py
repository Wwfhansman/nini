"""FastAPI application for the Nini Kitchen Agent backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend import database
from backend.agent import runtime
from backend.agent.schemas import ApiResponse, ChatRequest, ControlRequest, KnowledgeRecipeImportRequest
from backend.config import get_settings
from backend.skills import memory, recipe_knowledge
from backend.terminal import state as terminal_state


STATIC_DIR = Path(__file__).parent / "static"


def _init_runtime() -> None:
    settings = get_settings()
    database.init_db(settings.db_path)
    terminal_state.get_state(settings.default_terminal_id, db_path=settings.db_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_runtime()
    yield


app = FastAPI(title="Nini Kitchen Agent Backend", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
        "providers": {
            "qiniu_configured": settings.qiniu_configured,
            "agent_model_configured": bool(settings.model_agent),
            "vision_model_configured": bool(settings.model_vision),
            "base_url": settings.qiniu_base_url,
        },
    }


@app.get("/test-console", response_class=FileResponse)
def test_console() -> FileResponse:
    return FileResponse(STATIC_DIR / "test-console.html")


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
        "recipe_documents": database.list_recipe_documents(resolved_terminal_id, db_path=settings.db_path),
        "provider_logs": database.list_provider_logs(resolved_terminal_id, db_path=settings.db_path),
        "tool_events": events,
    }
    return ApiResponse(ok=True, data=data, state=state, events=events, error=None)


@app.post("/api/chat", response_model=ApiResponse)
def post_chat(request: ChatRequest) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_request = ChatRequest(
        terminal_id=request.terminal_id or settings.default_terminal_id,
        text=request.text,
        source=request.source,
    )
    result = runtime.handle_chat(resolved_request, db_path=settings.db_path)
    events = _public_events(result["events"])
    return ApiResponse(
        ok=True,
        data=result["data"],
        state=result["state"],
        events=events,
        error=None,
    )


@app.post("/api/vision", response_model=ApiResponse)
async def post_vision(
    terminal_id: Optional[str] = Form(default=None),
    purpose: str = Form(default="ingredients"),
    image: Optional[UploadFile] = File(default=None),
) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_terminal_id = terminal_id or settings.default_terminal_id
    image_bytes = None
    content_type = "image/jpeg"
    if image is not None:
        image_bytes = await image.read()
        content_type = image.content_type or content_type
    result = runtime.handle_vision(
        resolved_terminal_id,
        purpose=purpose,
        image_bytes=image_bytes,
        content_type=content_type,
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


@app.get("/api/export/memory", response_class=PlainTextResponse)
def export_memory(terminal_id: Optional[str] = Query(default=None)) -> PlainTextResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_terminal_id = terminal_id or settings.default_terminal_id
    markdown = memory.export_memory_markdown(resolved_terminal_id, db_path=settings.db_path)
    return PlainTextResponse(markdown, media_type="text/markdown")


@app.post("/api/knowledge/recipe", response_model=ApiResponse)
def import_recipe(request: KnowledgeRecipeImportRequest) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    terminal_id = request.terminal_id or settings.default_terminal_id
    document = recipe_knowledge.import_recipe_document(
        terminal_id=terminal_id,
        title=request.title,
        content=request.content,
        source_type=request.source_type,
        db_path=settings.db_path,
    )
    event = database.add_tool_event(
        terminal_id=terminal_id,
        event_type="agent_tool",
        name="recipe_knowledge_import",
        input_json={"title": request.title},
        output_json={"document_id": document["id"]},
        status="success",
        db_path=settings.db_path,
    )
    state = terminal_state.get_state(terminal_id, db_path=settings.db_path)
    return ApiResponse(
        ok=True,
        data={"document_id": document["id"]},
        state=state,
        events=_public_events([event]),
        error=None,
    )
