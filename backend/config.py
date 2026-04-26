"""Runtime configuration for the backend."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    demo_mode: str = "mock"
    db_path: str = "./data/nini.db"
    default_terminal_id: str = "demo-kitchen-001"
    qiniu_base_url: str = "https://api.qnaigc.com/v1"
    qiniu_api_key: str = ""
    model_fast_chat: str = ""
    model_vision: str = ""
    model_agent: str = ""
    model_agent_thinking: str = ""
    provider_timeout_seconds: float = 30.0
    enable_provider_logs: bool = True
    volc_asr_app_key: str = ""
    volc_asr_access_key: str = ""
    volc_asr_resource_id: str = ""
    volc_tts_app_id: str = ""
    volc_tts_access_token: str = ""
    volc_tts_cluster: str = ""
    volc_tts_resource_id: str = "seed-tts-1.0"
    volc_tts_voice_type: str = "zh_female_wanwanxiaohe_moon_bigtts"
    speech_provider_mode: str = "mock"
    speech_timeout_seconds: float = 30.0

    @property
    def qiniu_configured(self) -> bool:
        return bool(self.qiniu_api_key)

    @property
    def volc_tts_configured(self) -> bool:
        return bool(self.volc_tts_app_id and self.volc_tts_access_token and self.volc_tts_resource_id)

    @property
    def volc_asr_configured(self) -> bool:
        return bool(self.volc_asr_app_key and self.volc_asr_access_key and self.volc_asr_resource_id)


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _first_non_empty_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_settings() -> Settings:
    demo_mode = os.getenv("DEMO_MODE", "mock").strip().lower()
    if demo_mode not in {"mock", "hybrid", "real"}:
        demo_mode = "mock"
    speech_provider_mode = os.getenv("SPEECH_PROVIDER_MODE", "mock").strip().lower()
    if speech_provider_mode not in {"mock", "real", "auto"}:
        speech_provider_mode = "mock"
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        demo_mode=demo_mode,
        db_path=os.getenv("DB_PATH", "./data/nini.db"),
        default_terminal_id=os.getenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001"),
        qiniu_base_url=os.getenv("QINIU_BASE_URL", "https://api.qnaigc.com/v1").rstrip("/"),
        qiniu_api_key=os.getenv("QINIU_API_KEY", ""),
        model_fast_chat=os.getenv("MODEL_FAST_CHAT", ""),
        model_vision=os.getenv("MODEL_VISION", ""),
        model_agent=os.getenv("MODEL_AGENT", ""),
        model_agent_thinking=os.getenv("MODEL_AGENT_THINKING", ""),
        provider_timeout_seconds=_float_env("PROVIDER_TIMEOUT_SECONDS", 30.0),
        enable_provider_logs=_bool_env("ENABLE_PROVIDER_LOGS", True),
        volc_asr_app_key=os.getenv("VOLC_ASR_APP_KEY", ""),
        volc_asr_access_key=os.getenv("VOLC_ASR_ACCESS_KEY", ""),
        volc_asr_resource_id=os.getenv("VOLC_ASR_RESOURCE_ID", ""),
        volc_tts_app_id=os.getenv("VOLC_TTS_APP_ID", ""),
        volc_tts_access_token=_first_non_empty_env("VOLC_TTS_ACCESS_KEY", "VOLC_TTS_ACCESS_TOKEN"),
        volc_tts_cluster=os.getenv("VOLC_TTS_CLUSTER", ""),
        volc_tts_resource_id=os.getenv("VOLC_TTS_RESOURCE_ID", "seed-tts-1.0"),
        volc_tts_voice_type=os.getenv("VOLC_TTS_VOICE_TYPE", "zh_female_wanwanxiaohe_moon_bigtts"),
        speech_provider_mode=speech_provider_mode,
        speech_timeout_seconds=_float_env("SPEECH_TIMEOUT_SECONDS", 30.0),
    )
