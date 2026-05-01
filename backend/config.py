"""Runtime configuration for the backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_ENV_FILE_LOADED = False
_FALSE_ENV_VALUES = {"0", "false", "no", "off"}


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def _load_env_file() -> None:
    """Load repo-local .env values for local uvicorn runs.

    The loader is intentionally tiny: it only supports KEY=VALUE lines and never
    overrides values that were already exported in the shell. Tests skip this so
    local secrets do not leak into isolated monkeypatch environments.
    """

    global _ENV_FILE_LOADED
    if _ENV_FILE_LOADED:
        return
    _ENV_FILE_LOADED = True

    if os.getenv("NINI_LOAD_DOTENV", "1").strip().lower() in _FALSE_ENV_VALUES:
        return
    if "PYTEST_CURRENT_TEST" in os.environ:
        return

    repo_root = Path(__file__).resolve().parents[1]
    candidates = []
    for path in (Path.cwd() / ".env", repo_root / ".env"):
        if path not in candidates:
            candidates.append(path)

    env_path = next((path for path in candidates if path.is_file()), None)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        os.environ.setdefault(key, _strip_env_value(value))


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
    volc_asr_ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
    volc_asr_app_key: str = ""
    volc_asr_access_key: str = ""
    volc_asr_resource_id: str = "volc.bigasr.sauc.duration"
    volc_tts_app_id: str = ""
    volc_tts_access_token: str = ""
    volc_tts_cluster: str = ""
    volc_tts_resource_id: str = "seed-tts-1.0"
    volc_tts_voice_type: str = "zh_female_wanwanxiaohe_moon_bigtts"
    mimo_api_key: str = ""
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_tts_model: str = "mimo-v2.5-tts"
    mimo_tts_voice: str = "茉莉"
    mimo_tts_style: str = "温柔、清晰、像厨房里的智能助手，语速自然，提醒简洁。"
    speech_provider_mode: str = "mock"
    speech_tts_vendor: str = "bytedance"
    speech_timeout_seconds: float = 30.0
    voice_wake_words: tuple[str, ...] = ("妮妮", "腻妮", "nini")
    voice_active_idle_seconds: float = 25.0
    voice_sleep_seconds: float = 60.0

    @property
    def qiniu_configured(self) -> bool:
        return bool(self.qiniu_api_key)

    @property
    def volc_tts_configured(self) -> bool:
        return bool(self.volc_tts_app_id and self.volc_tts_access_token and self.volc_tts_resource_id)

    @property
    def volc_asr_configured(self) -> bool:
        return bool(self.volc_asr_app_key and self.volc_asr_access_key and self.volc_asr_resource_id)

    @property
    def mimo_tts_configured(self) -> bool:
        return bool(self.mimo_api_key)


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
    _load_env_file()
    demo_mode = os.getenv("DEMO_MODE", "mock").strip().lower()
    if demo_mode not in {"mock", "hybrid", "real"}:
        demo_mode = "mock"
    speech_provider_mode = os.getenv("SPEECH_PROVIDER_MODE", "mock").strip().lower()
    if speech_provider_mode not in {"mock", "real", "auto"}:
        speech_provider_mode = "mock"
    speech_tts_vendor = os.getenv("SPEECH_TTS_VENDOR", "bytedance").strip().lower()
    if speech_tts_vendor not in {"bytedance", "xiaomi", "mock"}:
        speech_tts_vendor = "bytedance"
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
        volc_asr_ws_url=os.getenv(
            "VOLC_ASR_WS_URL",
            "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
        ),
        volc_asr_app_key=_first_non_empty_env("VOLC_ASR_APP_ID", "VOLC_ASR_APP_KEY"),
        volc_asr_access_key=_first_non_empty_env("VOLC_ASR_ACCESS_TOKEN", "VOLC_ASR_ACCESS_KEY"),
        volc_asr_resource_id=os.getenv("VOLC_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration"),
        volc_tts_app_id=os.getenv("VOLC_TTS_APP_ID", ""),
        volc_tts_access_token=_first_non_empty_env("VOLC_TTS_ACCESS_KEY", "VOLC_TTS_ACCESS_TOKEN"),
        volc_tts_cluster=os.getenv("VOLC_TTS_CLUSTER", ""),
        volc_tts_resource_id=os.getenv("VOLC_TTS_RESOURCE_ID", "seed-tts-1.0"),
        volc_tts_voice_type=os.getenv("VOLC_TTS_VOICE_TYPE", "zh_female_wanwanxiaohe_moon_bigtts"),
        mimo_api_key=os.getenv("MIMO_API_KEY", ""),
        mimo_base_url=os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/"),
        mimo_tts_model=os.getenv("MIMO_TTS_MODEL", "mimo-v2.5-tts"),
        mimo_tts_voice=os.getenv("MIMO_TTS_VOICE", "茉莉"),
        mimo_tts_style=os.getenv(
            "MIMO_TTS_STYLE",
            "温柔、清晰、像厨房里的智能助手，语速自然，提醒简洁。",
        ),
        speech_provider_mode=speech_provider_mode,
        speech_tts_vendor=speech_tts_vendor,
        speech_timeout_seconds=_float_env("SPEECH_TIMEOUT_SECONDS", 30.0),
        voice_wake_words=tuple(
            word.strip()
            for word in os.getenv("VOICE_WAKE_WORDS", "妮妮,腻妮,nini").split(",")
            if word.strip()
        ),
        voice_active_idle_seconds=_float_env("VOICE_ACTIVE_IDLE_SECONDS", 25.0),
        voice_sleep_seconds=_float_env("VOICE_SLEEP_SECONDS", 60.0),
    )
