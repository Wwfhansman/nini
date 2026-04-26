"""Mock speech provider responses."""

from __future__ import annotations


def mock_tts_response() -> dict:
    return {
        "audio_base64": "",
        "mime_type": "audio/mpeg",
        "provider": "mock_tts",
        "voice_type": "mock",
    }


def mock_asr_response() -> dict:
    return {
        "text": "下一步",
        "provider": "mock_asr",
    }

