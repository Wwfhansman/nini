"""Xiaomi MiMo TTS provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from backend.config import Settings, get_settings
from backend.speech.schemas import SpeechProviderError, TTSResult


class MimoTTSProvider:
    name = "mimo_tts"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.mimo_tts_model

    def _validate_config(self) -> None:
        if not self.settings.mimo_api_key:
            raise SpeechProviderError("MIMO_API_KEY is required for Xiaomi MiMo TTS provider", self.name, self.model)

    def _payload(self, text: str) -> Dict[str, Any]:
        return {
            "model": self.settings.mimo_tts_model,
            "messages": [
                {
                    "role": "user",
                    "content": self.settings.mimo_tts_style,
                },
                {
                    "role": "assistant",
                    "content": text,
                },
            ],
            "audio": {
                "format": "wav",
                "voice": self.settings.mimo_tts_voice,
            },
        }

    def _parse_audio_base64(self, response_json: Dict[str, Any]) -> str:
        try:
            audio_base64 = response_json["choices"][0]["message"]["audio"]["data"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SpeechProviderError(
                "provider response missing choices[0].message.audio.data",
                self.name,
                self.model,
            ) from exc
        if not isinstance(audio_base64, str) or not audio_base64.strip():
            raise SpeechProviderError("provider response audio data is empty", self.name, self.model)
        return audio_base64

    def synthesize(self, text: str, terminal_id: str) -> TTSResult:
        self._validate_config()
        headers = {
            "api-key": self.settings.mimo_api_key,
            "Content-Type": "application/json",
        }
        url = f"{self.settings.mimo_base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.speech_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=self._payload(text))
                response.raise_for_status()
                audio_base64 = self._parse_audio_base64(response.json())
        except httpx.HTTPStatusError as exc:
            raise SpeechProviderError(
                exc.response.text[:500],
                self.name,
                self.model,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeechProviderError(str(exc), self.name, self.model) from exc
        except ValueError as exc:
            raise SpeechProviderError("provider returned non-JSON response", self.name, self.model) from exc

        return TTSResult(
            audio_base64=audio_base64,
            mime_type="audio/wav",
            provider=self.name,
            voice_type=self.settings.mimo_tts_voice,
        )
