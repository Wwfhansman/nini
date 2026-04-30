"""Streaming ASR provider boundary and mock implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional, Protocol

from backend.config import Settings, get_settings
from backend.speech.schemas import SpeechProviderError


PCM16_VOICE_ACTIVITY_THRESHOLD = 500


def pcm16_chunk_has_voice_activity(chunk: bytes) -> bool:
    sample_count = len(chunk) // 2
    if sample_count <= 0:
        return False
    for index in range(0, sample_count * 2, 2):
        sample = int.from_bytes(chunk[index : index + 2], "little", signed=True)
        if abs(sample) >= PCM16_VOICE_ACTIVITY_THRESHOLD:
            return True
    return False


@dataclass(frozen=True)
class StreamingASREvent:
    type: str
    text: str = ""
    provider: str = "mock_streaming_asr"
    final: bool = False
    fallback_used: bool = False


class StreamingASRSession(Protocol):
    provider: str
    model: str
    fallback_used: bool

    async def send_audio(self, chunk: bytes) -> None:
        ...

    async def finish(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def receive_event(self, timeout: Optional[float] = None) -> Optional[StreamingASREvent]:
        ...


class StreamingASRProvider(Protocol):
    name: str
    model: str

    async def start_session(self, terminal_id: str, sample_rate: int = 16000) -> StreamingASRSession:
        ...


class MockStreamingASRSession:
    provider = "mock_streaming_asr"
    model = "mock-streaming-asr"
    fallback_used = False

    def __init__(
        self,
        terminal_id: str,
        fallback_used: bool = False,
        auto_final_text: str = "妮妮，下一步",
        auto_finalize: bool = True,
    ) -> None:
        self.terminal_id = terminal_id
        self.fallback_used = fallback_used
        self.auto_final_text = auto_final_text
        self.auto_finalize = auto_finalize
        self._queue: asyncio.Queue[StreamingASREvent] = asyncio.Queue()
        self._closed = False
        self._received_audio = False
        self._partial_sent = False
        self._final_emitted = False
        self._audio_bytes = 0

    async def send_audio(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        if not pcm16_chunk_has_voice_activity(chunk):
            return
        self._received_audio = True
        self._audio_bytes += len(chunk)
        if not self.auto_finalize:
            return
        if not self._partial_sent:
            self._partial_sent = True
            await self.emit_partial("正在听")
        if not self._final_emitted and self._audio_bytes >= 16000:
            await self.emit_final(self.auto_final_text)

    async def emit_partial(self, text: str) -> None:
        await self._queue.put(
            StreamingASREvent(
                type="partial",
                text=text,
                provider=self.provider,
                fallback_used=self.fallback_used,
            )
        )

    async def emit_final(self, text: str) -> None:
        if self._closed:
            return
        self._final_emitted = True
        await self._queue.put(
            StreamingASREvent(
                type="final",
                text=text,
                provider=self.provider,
                final=True,
                fallback_used=self.fallback_used,
            )
        )

    async def finish(self) -> None:
        if self._closed:
            return
        if self._final_emitted:
            return
        if not self._received_audio:
            return
        if not self.auto_finalize:
            return
        await self.emit_final("下一步")

    async def close(self) -> None:
        self._closed = True

    async def receive_event(self, timeout: Optional[float] = None) -> Optional[StreamingASREvent]:
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class MockStreamingASRProvider:
    name = "mock_streaming_asr"
    model = "mock-streaming-asr"

    def __init__(self, fallback_used: bool = False, auto_finalize: Optional[bool] = None) -> None:
        self.fallback_used = fallback_used
        self.auto_finalize = not fallback_used if auto_finalize is None else auto_finalize

    async def start_session(self, terminal_id: str, sample_rate: int = 16000) -> MockStreamingASRSession:
        return MockStreamingASRSession(
            terminal_id,
            fallback_used=self.fallback_used,
            auto_finalize=self.auto_finalize,
        )


def get_streaming_asr_provider(settings: Optional[Settings] = None) -> StreamingASRProvider:
    settings = settings or get_settings()
    if settings.speech_provider_mode == "mock":
        return MockStreamingASRProvider()

    if not settings.volc_asr_configured:
        if settings.speech_provider_mode in {"auto", "real"}:
            return MockStreamingASRProvider(fallback_used=True)
        raise SpeechProviderError(
            "Volcengine ASR credentials are not configured",
            "volc_streaming_asr",
            "volc-bigmodel-streaming-asr",
        )

    from backend.speech.volc_streaming_asr import VolcStreamingASRProvider

    return VolcStreamingASRProvider(settings)
