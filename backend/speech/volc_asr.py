"""Volcengine ASR provider boundary.

The current sprint intentionally avoids the streaming WebSocket integration.
This class preserves the provider boundary and returns a structured error so
auto/real modes can fall back to mock ASR without breaking the demo.
"""

from __future__ import annotations

from typing import Optional

from backend.config import Settings, get_settings
from backend.speech.schemas import ASRResult, SpeechProviderError


class VolcASRProvider:
    name = "volc_asr"
    model = "volc-bigmodel-asr"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _validate_config(self) -> None:
        missing = []
        if not self.settings.volc_asr_app_key:
            missing.append("VOLC_ASR_APP_KEY")
        if not self.settings.volc_asr_access_key:
            missing.append("VOLC_ASR_ACCESS_KEY")
        if not self.settings.volc_asr_resource_id:
            missing.append("VOLC_ASR_RESOURCE_ID")
        if missing:
            raise SpeechProviderError(
                f"{', '.join(missing)} required for Volcengine ASR provider",
                self.name,
                self.model,
            )

    def transcribe(
        self,
        audio_bytes: Optional[bytes],
        content_type: str = "audio/wav",
        terminal_id: str = "demo-kitchen-001",
    ) -> ASRResult:
        self._validate_config()
        if not audio_bytes:
            raise SpeechProviderError("audio bytes are required for Volcengine ASR provider", self.name, self.model)
        raise SpeechProviderError(
            "Volcengine non-streaming ASR is not implemented in this phase; use mock fallback",
            self.name,
            self.model,
        )

