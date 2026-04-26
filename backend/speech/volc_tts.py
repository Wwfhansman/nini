"""Volcengine Doubao TTS provider."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any, Dict, Optional

import httpx

from backend.config import Settings, get_settings
from backend.speech.schemas import SpeechProviderError, TTSResult


VOLC_TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
SUCCESS_CODES = {0, 20000000, "0", "20000000"}


class VolcTTSProvider:
    name = "volc_tts"
    model = "doubao-tts-1.0"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _validate_config(self) -> None:
        missing = []
        if not self.settings.volc_tts_app_id:
            missing.append("VOLC_TTS_APP_ID")
        if not self.settings.volc_tts_access_token:
            missing.append("VOLC_TTS_ACCESS_KEY or VOLC_TTS_ACCESS_TOKEN")
        if not self.settings.volc_tts_resource_id:
            missing.append("VOLC_TTS_RESOURCE_ID")
        if missing:
            raise SpeechProviderError(
                f"{', '.join(missing)} required for Volcengine TTS provider",
                self.name,
                self.model,
            )

    def _payload(self, text: str, terminal_id: str) -> Dict[str, Any]:
        return {
            "user": {"uid": terminal_id},
            "req_params": {
                "text": text,
                "speaker": self.settings.volc_tts_voice_type,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000,
                },
            },
        }

    def _parse_audio_base64(self, response_text: str) -> str:
        payloads = []
        for line in response_text.splitlines():
            content = line.strip()
            if not content:
                continue
            if content.startswith("data:"):
                content = content.removeprefix("data:").strip()
            try:
                payloads.append(json.loads(content))
            except json.JSONDecodeError:
                continue
        if not payloads:
            try:
                payloads.append(json.loads(response_text))
            except json.JSONDecodeError as exc:
                raise SpeechProviderError("provider returned non-JSON response", self.name, self.model) from exc

        audio_bytes = bytearray()
        last_error = None
        for payload in payloads:
            code = payload.get("code")
            if code not in SUCCESS_CODES and code is not None:
                last_error = payload
                continue
            data = payload.get("data") or payload.get("audio_base64")
            if not data:
                continue
            if not isinstance(data, str):
                raise SpeechProviderError("provider response audio data is not base64 text", self.name, self.model)
            try:
                audio_bytes.extend(base64.b64decode(data))
            except ValueError as exc:
                raise SpeechProviderError("provider returned invalid base64 audio data", self.name, self.model) from exc
        if audio_bytes:
            return base64.b64encode(bytes(audio_bytes)).decode("ascii")
        if last_error is not None:
            message = str(last_error.get("message") or last_error.get("msg") or last_error)[:500]
            raise SpeechProviderError(message, self.name, self.model)
        raise SpeechProviderError("provider response missing base64 audio data", self.name, self.model)

    def synthesize(self, text: str, terminal_id: str) -> TTSResult:
        self._validate_config()
        request_id = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "X-Api-App-Id": self.settings.volc_tts_app_id,
            "X-Api-Access-Key": self.settings.volc_tts_access_token,
            "X-Api-Resource-Id": self.settings.volc_tts_resource_id,
            "X-Api-Request-Id": request_id,
        }
        try:
            with httpx.Client(timeout=self.settings.speech_timeout_seconds) as client:
                response = client.post(VOLC_TTS_ENDPOINT, headers=headers, json=self._payload(text, terminal_id))
                response.raise_for_status()
                audio_base64 = self._parse_audio_base64(response.text)
        except httpx.HTTPStatusError as exc:
            raise SpeechProviderError(
                exc.response.text[:500],
                self.name,
                self.model,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeechProviderError(str(exc), self.name, self.model) from exc
        return TTSResult(
            audio_base64=audio_base64,
            mime_type="audio/mpeg",
            provider=self.name,
            voice_type=self.settings.volc_tts_voice_type,
        )
