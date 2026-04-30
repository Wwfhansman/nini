"""Speech provider selection and mock implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.config import Settings, get_settings
from backend.mocks.speech_responses import mock_asr_response, mock_tts_response
from backend.speech.schemas import ASRResult, TTSResult
from backend.speech.mimo_tts import MimoTTSProvider
from backend.speech.volc_asr import VolcASRProvider
from backend.speech.volc_tts import VolcTTSProvider


@dataclass
class MockTTSProvider:
    name: str = "mock_tts"
    model: str = "mock-tts"

    def synthesize(self, text: str, terminal_id: str) -> TTSResult:
        return TTSResult(**mock_tts_response(), fallback_used=False)


@dataclass
class MockASRProvider:
    name: str = "mock_asr"
    model: str = "mock-asr"

    def transcribe(
        self,
        audio_bytes: Optional[bytes],
        content_type: str = "audio/wav",
        terminal_id: str = "demo-kitchen-001",
    ) -> ASRResult:
        return ASRResult(**mock_asr_response(), fallback_used=False)


def get_tts_provider(settings: Optional[Settings] = None, tts_vendor: Optional[str] = None):
    settings = settings or get_settings()
    vendor = (tts_vendor or settings.speech_tts_vendor or "bytedance").strip().lower()
    if vendor not in {"bytedance", "xiaomi", "mock"}:
        vendor = settings.speech_tts_vendor
    if settings.speech_provider_mode == "mock" or vendor == "mock":
        return MockTTSProvider()
    if vendor == "xiaomi":
        return MimoTTSProvider(settings)
    return VolcTTSProvider(settings)


def get_asr_provider(settings: Optional[Settings] = None):
    settings = settings or get_settings()
    if settings.speech_provider_mode == "mock":
        return MockASRProvider()
    return VolcASRProvider(settings)
