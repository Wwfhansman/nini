"""Speech request/result schemas and provider errors."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TTSRequest(BaseModel):
    terminal_id: Optional[str] = None
    text: str


class TTSResult(BaseModel):
    audio_base64: str = ""
    mime_type: str = "audio/mpeg"
    provider: str
    voice_type: Optional[str] = None
    fallback_used: bool = False
    error: Optional[str] = None


class ASRResult(BaseModel):
    text: str
    provider: str
    fallback_used: bool = False
    error: Optional[str] = None


class SpeechProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        provider: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code

