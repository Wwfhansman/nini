"""FastAPI application for the Nini Kitchen Agent backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Query, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend import database
from backend.agent import runtime
from backend.agent.schemas import ApiResponse, ChatRequest, ControlRequest, KnowledgeRecipeImportRequest
from backend.config import get_settings
from backend.skills import memory, recipe_knowledge
from backend.speech.providers import MockASRProvider, MockTTSProvider, get_asr_provider, get_tts_provider
from backend.speech.schemas import SpeechProviderError, TTSRequest
from backend.terminal import state as terminal_state
from backend.voice.session import VoiceWebSocketSession


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


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _api_error(status_code: int, code: str, message: str, state: Dict[str, Any]) -> JSONResponse:
    payload = ApiResponse(
        ok=False,
        data=None,
        state=state,
        events=[],
        error={"code": code, "message": message},
    )
    return JSONResponse(status_code=status_code, content=_model_to_dict(payload))


def _record_provider_log(
    terminal_id: str,
    provider: str,
    model: Optional[str],
    status: str,
    latency_ms: int,
    error: Optional[str] = None,
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
        db_path=settings.db_path,
    )


def _clean_tts_vendor(value: Optional[str], default: str = "bytedance") -> str:
    vendor = (value or default or "bytedance").strip().lower()
    if vendor not in {"bytedance", "xiaomi", "mock"}:
        return default if default in {"bytedance", "xiaomi", "mock"} else "bytedance"
    return vendor


def _resolve_tts_vendor(requested: Optional[str], configured: str) -> str:
    if requested and requested.strip():
        return _clean_tts_vendor(requested, "bytedance")
    return _clean_tts_vendor(configured, "bytedance")


def _sanitize_speech_error(message: str, settings: Any) -> str:
    sanitized = message or ""
    for secret in (
        settings.volc_tts_app_id,
        settings.volc_tts_access_token,
        settings.volc_asr_app_key,
        settings.volc_asr_access_key,
        settings.mimo_api_key,
    ):
        if secret:
            sanitized = sanitized.replace(secret, "***")
    return sanitized[:500]


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
            "speech_provider_mode": settings.speech_provider_mode,
            "tts_vendor": settings.speech_tts_vendor,
            "volc_tts_configured": settings.volc_tts_configured,
            "mimo_tts_configured": settings.mimo_tts_configured,
            "volc_asr_configured": settings.volc_asr_configured,
            "tts_voice_type": settings.volc_tts_voice_type,
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


@app.post("/api/speech/tts", response_model=ApiResponse)
def post_speech_tts(request: TTSRequest):
    settings = get_settings()
    database.init_db(settings.db_path)
    terminal_id = request.terminal_id or settings.default_terminal_id
    state = terminal_state.get_state(terminal_id, db_path=settings.db_path)
    text = request.text.strip()
    if not text:
        return _api_error(400, "invalid_request", "text is required", state)
    if len(text) > 300:
        return _api_error(400, "invalid_request", "text must be 300 characters or fewer", state)

    requested_tts_vendor = _resolve_tts_vendor(request.tts_vendor, settings.speech_tts_vendor)
    provider = get_tts_provider(settings, requested_tts_vendor)
    fallback_error: Optional[str] = None
    start_ms = time.perf_counter()
    try:
        result = provider.synthesize(text, terminal_id)
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        status = "success"
        if not isinstance(provider, MockTTSProvider):
            _record_provider_log(terminal_id, provider.name, provider.model, status, latency_ms)
    except SpeechProviderError as exc:
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        fallback_error = _sanitize_speech_error(str(exc), settings)
        _record_provider_log(terminal_id, exc.provider, exc.model, "error", latency_ms, fallback_error)
        result = MockTTSProvider().synthesize(text, terminal_id)
        result.fallback_used = True
        result.error = fallback_error
        status = "fallback"

    result_dict = _model_to_dict(result)
    event = database.add_tool_event(
        terminal_id=terminal_id,
        event_type="agent_tool",
        name="speech_tts",
        input_json={"text_length": len(text), "requested_tts_vendor": requested_tts_vendor},
        output_json={
            "provider": result.provider,
            "requested_tts_vendor": requested_tts_vendor,
            "attempted_provider": getattr(provider, "name", result.provider),
            "status": status,
            "latency_ms": latency_ms,
            "mime_type": result.mime_type,
            "audio_present": bool(result.audio_base64),
            "fallback_used": result.fallback_used,
            "error": fallback_error[:500] if fallback_error else None,
        },
        status=status,
        db_path=settings.db_path,
    )
    return ApiResponse(ok=True, data=result_dict, state=state, events=_public_events([event]), error=None)


@app.post("/api/speech/asr", response_model=ApiResponse)
async def post_speech_asr(
    terminal_id: Optional[str] = Form(default=None),
    audio: Optional[UploadFile] = File(default=None),
) -> ApiResponse:
    settings = get_settings()
    database.init_db(settings.db_path)
    resolved_terminal_id = terminal_id or settings.default_terminal_id
    state = terminal_state.get_state(resolved_terminal_id, db_path=settings.db_path)
    audio_bytes = None
    content_type = "audio/wav"
    if audio is not None:
        audio_bytes = await audio.read()
        content_type = audio.content_type or content_type

    provider = get_asr_provider(settings)
    fallback_error: Optional[str] = None
    start_ms = time.perf_counter()
    try:
        result = provider.transcribe(audio_bytes, content_type=content_type, terminal_id=resolved_terminal_id)
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        status = "success"
        if not isinstance(provider, MockASRProvider):
            _record_provider_log(resolved_terminal_id, provider.name, provider.model, status, latency_ms)
    except SpeechProviderError as exc:
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        fallback_error = str(exc)
        _record_provider_log(resolved_terminal_id, exc.provider, exc.model, "error", latency_ms, fallback_error)
        result = MockASRProvider().transcribe(audio_bytes, content_type=content_type, terminal_id=resolved_terminal_id)
        result.fallback_used = True
        result.error = fallback_error
        status = "fallback"

    result_dict = _model_to_dict(result)
    event = database.add_tool_event(
        terminal_id=resolved_terminal_id,
        event_type="agent_tool",
        name="speech_asr",
        input_json={"content_type": content_type, "audio_bytes": len(audio_bytes or b"")},
        output_json={
            "provider": result.provider,
            "attempted_provider": getattr(provider, "name", result.provider),
            "status": status,
            "latency_ms": latency_ms,
            "text": result.text,
            "fallback_used": result.fallback_used,
            "error": fallback_error[:500] if fallback_error else None,
        },
        status=status,
        db_path=settings.db_path,
    )
    return ApiResponse(ok=True, data=result_dict, state=state, events=_public_events([event]), error=None)


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    session = VoiceWebSocketSession(websocket)
    await session.run()


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
