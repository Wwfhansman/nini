"""WebSocket voice session orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from backend import database
from backend.agent import runtime
from backend.agent.schemas import ChatRequest
from backend.agent.voice_router import route_voice_text
from backend.config import Settings, get_settings
from backend.speech.schemas import SpeechProviderError
from backend.speech.streaming_asr import (
    MockStreamingASRProvider,
    MockStreamingASRSession,
    StreamingASREvent,
    StreamingASRSession,
    get_streaming_asr_provider,
    pcm16_chunk_has_voice_activity,
)
from backend.terminal import state as terminal_state
from backend.voice.schemas import VoiceClientMessage, VoiceState


TRAILING_PUNCTUATION = "。！？!?.,，；;：:、 \t\r\n"
ASR_FINAL_FALLBACK_SECONDS = 1.2
WAKE_FREE_COOKING_COMMANDS = {
    "next_step",
    "previous_step",
    "pause",
    "resume",
    "repeat_current_step",
    "finish",
}


def public_event(event: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(event)
    public["input"] = public.pop("input_json", None)
    public["output"] = public.pop("output_json", None)
    return public


def public_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [public_event(event) for event in events]


def sanitize_provider_error(message: str, settings: Settings) -> str:
    sanitized = message or "语音识别服务暂时不可用。"
    for secret in (settings.volc_asr_app_key, settings.volc_asr_access_key):
        if secret:
            sanitized = sanitized.replace(secret, "***")
    return sanitized[:500]


def strip_wake_word(text: str, wake_words: tuple[str, ...]) -> tuple[bool, str]:
    original = (text or "").strip()
    if not original:
        return False, ""
    folded = original.lower()
    earliest: Optional[tuple[int, str]] = None
    for word in wake_words:
        candidate = word.strip()
        if not candidate:
            continue
        index = folded.find(candidate.lower())
        if index < 0:
            continue
        if earliest is None or index < earliest[0]:
            earliest = (index, candidate)
    if earliest is None:
        return False, original.strip(TRAILING_PUNCTUATION)

    index, word = earliest
    remainder = original[index + len(word) :].strip(TRAILING_PUNCTUATION)
    return True, remainder


class VoiceWebSocketSession:
    def __init__(self, websocket: WebSocket, settings: Optional[Settings] = None) -> None:
        self.websocket = websocket
        self.settings = settings or get_settings()
        self.terminal_id = self.settings.default_terminal_id
        self.sample_rate = 16000
        self.state: VoiceState = "listening_for_wake"
        self.asr_session: Optional[StreamingASRSession] = None
        self.started = False
        self.closed = False
        self.send_lock = asyncio.Lock()
        now = time.monotonic()
        self.last_activity_at = now
        self.last_effective_final_at = now
        self.last_partial_text = ""
        self.waiting_for_asr_final = False
        self.final_fallback_task: Optional[asyncio.Task[None]] = None

    async def run(self) -> None:
        await self.websocket.accept()
        database.init_db(self.settings.db_path)
        terminal_state.get_state(self.terminal_id, db_path=self.settings.db_path)
        timeout_task = asyncio.create_task(self._timeout_loop())
        asr_task = asyncio.create_task(self._asr_event_loop())
        try:
            await self._receive_loop()
        finally:
            self.closed = True
            timeout_task.cancel()
            asr_task.cancel()
            self._cancel_final_fallback()
            if self.asr_session:
                await self.asr_session.close()

    async def _send(self, payload: Dict[str, Any]) -> None:
        if self.closed:
            return
        async with self.send_lock:
            if self.closed:
                return
            try:
                await self.websocket.send_json(payload)
            except WebSocketDisconnect:
                self.closed = True
            except RuntimeError as exc:
                message = str(exc).lower()
                if "disconnect" in message or "websocket" in message:
                    self.closed = True
                    return
                raise

    async def _send_state(self, state: VoiceState) -> None:
        self.state = state
        await self._send({"type": "session.state", "state": state})

    async def _start_asr_session(self, fallback_message: Optional[str] = None) -> None:
        self._cancel_final_fallback()
        self.waiting_for_asr_final = False
        self.last_partial_text = ""
        if self.asr_session:
            await self.asr_session.close()
            self.asr_session = None

        provider = get_streaming_asr_provider(self.settings)
        try:
            self.asr_session = await provider.start_session(self.terminal_id, self.sample_rate)
        except SpeechProviderError as exc:
            self.asr_session = await MockStreamingASRProvider(fallback_used=True).start_session(
                self.terminal_id,
                self.sample_rate,
            )
            safe_message = sanitize_provider_error(str(exc), self.settings)
            await self._send(
                {
                    "type": "error",
                    "message": f"在线语音识别暂不可用，已切换演示模式：{safe_message}",
                }
            )

        provider_name = getattr(self.asr_session, "provider", "mock_streaming_asr")
        await self._send(
            {
                "type": "asr.provider",
                "provider": provider_name,
                "fallback_used": bool(getattr(self.asr_session, "fallback_used", False)),
                "message": fallback_message,
            }
        )

    def _cancel_final_fallback(self) -> None:
        task = self.final_fallback_task
        self.final_fallback_task = None
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()

    def _schedule_final_from_partial(self, session: StreamingASRSession) -> None:
        self._cancel_final_fallback()

        async def emit_final_if_needed() -> None:
            await asyncio.sleep(ASR_FINAL_FALLBACK_SECONDS)
            if self.closed or self.asr_session is not session or not self.waiting_for_asr_final:
                return
            text = self.last_partial_text.strip()
            if text:
                await self._handle_asr_event(
                    StreamingASREvent(
                        type="final",
                        text=text,
                        provider=getattr(session, "provider", "streaming_asr"),
                        final=True,
                        fallback_used=bool(getattr(session, "fallback_used", False)),
                    )
                )
                return
            self.waiting_for_asr_final = False
            if self.asr_session is session and not isinstance(session, MockStreamingASRSession):
                await session.close()
                self.asr_session = None

        self.final_fallback_task = asyncio.create_task(emit_final_if_needed())

    async def _finish_current_utterance(self) -> None:
        session = self.asr_session
        if not session or self.waiting_for_asr_final:
            return
        self.waiting_for_asr_final = True
        try:
            await session.finish()
        except SpeechProviderError as exc:
            self.waiting_for_asr_final = False
            await self._switch_to_mock_after_provider_error(exc)
            return
        except Exception as exc:
            self.waiting_for_asr_final = False
            await self._switch_to_mock_after_provider_error(
                SpeechProviderError(
                    f"streaming ASR finish failed: {exc}",
                    getattr(session, "provider", "streaming_asr"),
                    getattr(session, "model", None),
                )
            )
            return
        self._schedule_final_from_partial(session)

    def _should_start_asr_on_session_start(self) -> bool:
        if self.settings.speech_provider_mode == "mock":
            return True
        return not self.settings.volc_asr_configured

    async def _receive_loop(self) -> None:
        while not self.closed:
            try:
                message = await self.websocket.receive()
            except WebSocketDisconnect:
                break
            msg_type = message.get("type")
            if msg_type == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                await self._handle_audio(message["bytes"])
                continue
            if "text" in message and message["text"] is not None:
                await self._handle_text_message(message["text"])

    async def _handle_text_message(self, raw_text: str) -> None:
        try:
            payload = json.loads(raw_text)
            msg = VoiceClientMessage(**payload)
        except Exception:
            await self._send({"type": "error", "message": "语音会话消息格式无效。"})
            return

        if msg.type == "session.start":
            self.terminal_id = msg.terminal_id or self.settings.default_terminal_id
            self.sample_rate = int(msg.sample_rate or 16000)
            database.init_db(self.settings.db_path)
            terminal_state.get_state(self.terminal_id, db_path=self.settings.db_path)
            now = time.monotonic()
            self.last_activity_at = now
            self.last_effective_final_at = now
            self.started = True
            if self._should_start_asr_on_session_start():
                await self._start_asr_session()
            else:
                await self._send(
                    {
                        "type": "asr.provider",
                        "provider": "volc_streaming_asr",
                        "fallback_used": False,
                        "message": "waiting_for_audio",
                    }
                )
            await self._send_state("listening_for_wake")
            return

        if msg.type == "session.stop":
            self.last_activity_at = time.monotonic()
            await self._finish_current_utterance()
            return

        if msg.type in {"audio.end", "utterance.end"}:
            self.last_activity_at = time.monotonic()
            await self._finish_current_utterance()
            return

        if msg.type == "session.sleep":
            await self._sleep()
            return

        if msg.type == "asr.inject_final":
            can_inject = (
                isinstance(self.asr_session, MockStreamingASRSession)
                or self.settings.speech_provider_mode == "mock"
            )
            if can_inject and msg.text:
                await self._handle_asr_event(
                    StreamingASREvent(
                        type="final",
                        text=msg.text,
                        provider="mock_streaming_asr",
                        final=True,
                        fallback_used=bool(getattr(self.asr_session, "fallback_used", False)),
                    )
                )
            else:
                await self._send({"type": "error", "message": "仅演示识别支持注入转写文本。"})
            return

        await self._send({"type": "error", "message": f"不支持的语音会话消息：{msg.type}"})

    async def _handle_audio(self, chunk: bytes) -> None:
        if not self.started or self.state == "sleeping":
            return
        if self.waiting_for_asr_final:
            return
        if not pcm16_chunk_has_voice_activity(chunk):
            return
        self.last_activity_at = time.monotonic()
        if not self.asr_session:
            await self._start_asr_session()
        if self.asr_session:
            try:
                await self.asr_session.send_audio(chunk)
            except SpeechProviderError as exc:
                await self._switch_to_mock_after_provider_error(exc)
            except Exception as exc:
                provider = getattr(self.asr_session, "provider", "streaming_asr")
                model = getattr(self.asr_session, "model", None)
                await self._switch_to_mock_after_provider_error(
                    SpeechProviderError(
                        f"streaming ASR send failed: {exc}",
                        provider,
                        model,
                    )
                )

    async def _asr_event_loop(self) -> None:
        while not self.closed:
            await asyncio.sleep(0)
            session = self.asr_session
            if not session:
                await asyncio.sleep(0.05)
                continue
            event = await session.receive_event(timeout=0.2)
            if event is None:
                continue
            await self._handle_asr_event(event)

    async def _handle_asr_event(self, event: StreamingASREvent) -> None:
        if event.type == "error":
            await self._switch_to_mock_after_provider_error(
                SpeechProviderError(event.text, event.provider, getattr(self.asr_session, "model", None))
            )
            return
        text = (event.text or "").strip()
        if not text:
            return
        if event.type == "partial":
            self.last_activity_at = time.monotonic()
            self.last_partial_text = text
            await self._send({"type": "asr.partial", "text": text})
            return
        if event.type == "final":
            session = self.asr_session
            self.waiting_for_asr_final = False
            self.last_partial_text = ""
            self._cancel_final_fallback()
            await self._send({"type": "asr.final", "text": text})
            await self._handle_final_text(text)
            if session is self.asr_session and session:
                await session.close()
                self.asr_session = None

    async def _switch_to_mock_after_provider_error(self, exc: SpeechProviderError) -> None:
        self._cancel_final_fallback()
        self.waiting_for_asr_final = False
        self.last_partial_text = ""
        if self.asr_session:
            await self.asr_session.close()
        self.asr_session = await MockStreamingASRProvider(fallback_used=True).start_session(
            self.terminal_id,
            self.sample_rate,
        )
        await self._send(
            {
                "type": "error",
                "message": f"在线语音识别中断，已切换演示模式：{sanitize_provider_error(str(exc), self.settings)}",
            }
        )
        await self._send(
            {
                "type": "asr.provider",
                "provider": "mock_streaming_asr",
                "fallback_used": True,
            }
        )

    async def _handle_final_text(self, text: str) -> None:
        if self.state == "sleeping":
            return
        now = time.monotonic()
        self.last_activity_at = now

        command_text = text.strip()
        if self.state == "listening_for_wake":
            detected, remainder = strip_wake_word(command_text, self.settings.voice_wake_words)
            if not detected:
                handled = await self._handle_wake_free_cooking_command(command_text)
                if handled:
                    self.last_effective_final_at = now
                return
            self.last_effective_final_at = now
            await self._send({"type": "wake.detected", "text": text})
            await self._send_state("active_listening")
            command_text = remainder
        else:
            detected, remainder = strip_wake_word(command_text, self.settings.voice_wake_words)
            if detected and remainder:
                command_text = remainder
            self.last_effective_final_at = now

        command_text = command_text.strip(TRAILING_PUNCTUATION)
        if command_text:
            await self._handle_agent_command(command_text)

    async def _handle_wake_free_cooking_command(self, text: str) -> bool:
        """Allow unprefixed hands-free P0 controls while the cooking screen is active."""
        try:
            terminal_snapshot = terminal_state.get_state(self.terminal_id, db_path=self.settings.db_path)
        except Exception:
            return False
        if terminal_snapshot.get("ui_mode") != "cooking":
            return False
        route = route_voice_text(text, terminal_snapshot)
        if route.route != "local_control" or route.command not in WAKE_FREE_COOKING_COMMANDS:
            return False
        await self._send_state("active_listening")
        await self._handle_agent_command(text.strip(TRAILING_PUNCTUATION))
        return True

    async def _handle_agent_command(self, text: str) -> None:
        await self._send_state("thinking")
        try:
            result = await asyncio.to_thread(
                runtime.handle_chat,
                ChatRequest(terminal_id=self.terminal_id, text=text, source="voice_session"),
                self.settings.db_path,
            )
        except Exception as exc:
            await self._send({"type": "error", "message": f"语音指令处理失败：{str(exc)[:300]}"})
            await self._send_state("active_listening")
            return

        events = public_events(result.get("events", []))
        for event in events:
            await self._send({"type": "agent.event", "event": event})

        data = result.get("data") or {}
        response_payload = {
            "type": "agent.response",
            "speech": data.get("speech", ""),
            "data": data,
            "state": result.get("state", {}),
            "events": events,
        }
        await self._send(response_payload)
        self.last_activity_at = time.monotonic()
        self.last_effective_final_at = self.last_activity_at
        await self._send_state("active_listening")

    async def _timeout_loop(self) -> None:
        while not self.closed:
            await asyncio.sleep(1)
            if not self.started or self.state == "sleeping":
                continue
            now = time.monotonic()
            if self.state == "active_listening" and now - self.last_effective_final_at >= self.settings.voice_active_idle_seconds:
                await self._send_state("listening_for_wake")
            if now - self.last_activity_at >= self.settings.voice_sleep_seconds:
                await self._sleep()

    async def _sleep(self) -> None:
        self._cancel_final_fallback()
        self.waiting_for_asr_final = False
        self.last_partial_text = ""
        if self.asr_session:
            await self.asr_session.close()
            self.asr_session = None
        self.started = False
        await self._send_state("sleeping")
