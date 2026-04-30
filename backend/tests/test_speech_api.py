from fastapi.testclient import TestClient

from backend.app import app
from backend.config import get_settings
from backend.speech.mimo_tts import MimoTTSProvider
from backend.speech.volc_tts import VOLC_TTS_ENDPOINT, VolcTTSProvider


def _client(tmp_path, monkeypatch, *, speech_mode: str = "mock"):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-speech-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", speech_mode)
    for name in [
        "VOLC_ASR_APP_KEY",
        "VOLC_ASR_ACCESS_KEY",
        "VOLC_ASR_RESOURCE_ID",
        "VOLC_TTS_APP_ID",
        "VOLC_TTS_ACCESS_KEY",
        "VOLC_TTS_ACCESS_TOKEN",
        "VOLC_TTS_RESOURCE_ID",
        "VOLC_TTS_CLUSTER",
        "SPEECH_TTS_VENDOR",
        "MIMO_API_KEY",
        "MIMO_BASE_URL",
        "MIMO_TTS_MODEL",
        "MIMO_TTS_VOICE",
        "MIMO_TTS_STYLE",
    ]:
        monkeypatch.delenv(name, raising=False)
    return TestClient(app)


def test_speech_tts_rejects_empty_text(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/speech/tts", json={"terminal_id": "demo-kitchen-001", "text": "  "})

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "text is required" in payload["error"]["message"]


def test_speech_tts_rejects_long_text(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/speech/tts", json={"terminal_id": "demo-kitchen-001", "text": "进" * 301})

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert "300" in payload["error"]["message"]


def test_mock_speech_tts_success_records_event(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/speech/tts", json={"terminal_id": "demo-kitchen-001", "text": "进入下一步。"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["provider"] == "mock_tts"
    assert payload["data"]["audio_base64"] == ""
    assert payload["data"]["mime_type"] == "audio/mpeg"
    assert payload["events"][0]["name"] == "speech_tts"
    assert payload["events"][0]["output"]["audio_present"] is False
    assert "audio_base64" not in payload["events"][0]["output"]

    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    assert "speech_tts" in [event["name"] for event in state_payload["tool_events"]]


def test_mock_speech_asr_success_returns_text(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/speech/asr",
        data={"terminal_id": "demo-kitchen-001"},
        files={"audio": ("mock.wav", b"mock", "audio/wav")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["provider"] == "mock_asr"
    assert payload["data"]["text"] == "下一步"
    assert payload["events"][0]["name"] == "speech_asr"
    assert payload["events"][0]["output"]["text"] == "下一步"


def test_real_speech_tts_missing_key_falls_back_without_500(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, speech_mode="real")

    response = client.post("/api/speech/tts", json={"terminal_id": "demo-kitchen-001", "text": "进入下一步。"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"] == "mock_tts"
    assert payload["data"]["fallback_used"] is True
    assert "VOLC_TTS_APP_ID" in payload["data"]["error"]
    assert payload["events"][0]["status"] == "fallback"
    assert payload["events"][0]["output"]["attempted_provider"] == "volc_tts"

    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    provider_logs = state_payload["provider_logs"]
    assert provider_logs[-1]["provider"] == "volc_tts"
    assert provider_logs[-1]["status"] == "error"


def test_real_speech_asr_missing_key_falls_back_without_500(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, speech_mode="real")

    response = client.post(
        "/api/speech/asr",
        data={"terminal_id": "demo-kitchen-001"},
        files={"audio": ("mock.wav", b"mock", "audio/wav")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"] == "mock_asr"
    assert payload["data"]["fallback_used"] is True
    assert "VOLC_ASR_APP_KEY" in payload["data"]["error"]
    assert payload["events"][0]["status"] == "fallback"
    assert payload["events"][0]["output"]["attempted_provider"] == "volc_asr"


def test_tts_legacy_token_is_used_when_new_key_is_blank(monkeypatch):
    monkeypatch.setenv("VOLC_TTS_APP_ID", "tts-app")
    monkeypatch.setenv("VOLC_TTS_ACCESS_KEY", "")
    monkeypatch.setenv("VOLC_TTS_ACCESS_TOKEN", "legacy-token")
    monkeypatch.setenv("VOLC_TTS_RESOURCE_ID", "seed-tts-1.0")

    settings = get_settings()

    assert settings.volc_tts_access_token == "legacy-token"
    assert settings.volc_tts_configured is True


def test_mimo_tts_settings_are_read(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")
    monkeypatch.setenv("SPEECH_TTS_VENDOR", "xiaomi")

    settings = get_settings()

    assert settings.mimo_tts_configured is True
    assert settings.speech_tts_vendor == "xiaomi"


def test_mimo_tts_provider_parses_success_response(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")
    monkeypatch.setenv("MIMO_TTS_VOICE", "茉莉")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "audio": {
                                "data": "base64audio",
                            }
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers=None, json=None):
            assert url == "https://api.xiaomimimo.com/v1/chat/completions"
            assert headers["api-key"] == "mimo-key"
            assert json["model"] == "mimo-v2.5-tts"
            assert json["messages"][0]["role"] == "user"
            assert json["messages"][1] == {"role": "assistant", "content": "进入下一步。"}
            assert json["audio"] == {"format": "wav", "voice": "茉莉"}
            return FakeResponse()

    monkeypatch.setattr("backend.speech.mimo_tts.httpx.Client", FakeClient)

    result = MimoTTSProvider(get_settings()).synthesize("进入下一步。", "demo-kitchen-001")

    assert result.provider == "mimo_tts"
    assert result.audio_base64 == "base64audio"
    assert result.mime_type == "audio/wav"


def test_speech_tts_xiaomi_vendor_uses_mimo_provider(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, speech_mode="real")
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"audio": {"data": "base64audio"}}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers=None, json=None):
            assert headers["api-key"] == "mimo-key"
            return FakeResponse()

    monkeypatch.setattr("backend.speech.mimo_tts.httpx.Client", FakeClient)

    response = client.post(
        "/api/speech/tts",
        json={"terminal_id": "demo-kitchen-001", "text": "进入下一步。", "tts_vendor": "xiaomi"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"] == "mimo_tts"
    assert payload["data"]["audio_base64"] == "base64audio"
    assert payload["data"]["mime_type"] == "audio/wav"
    assert payload["events"][0]["output"]["requested_tts_vendor"] == "xiaomi"
    assert payload["events"][0]["output"]["attempted_provider"] == "mimo_tts"


def test_speech_tts_xiaomi_missing_key_falls_back_without_leaking_secret(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, speech_mode="real")

    response = client.post(
        "/api/speech/tts",
        json={"terminal_id": "demo-kitchen-001", "text": "进入下一步。", "tts_vendor": "xiaomi"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"] == "mock_tts"
    assert payload["data"]["fallback_used"] is True
    assert "MIMO_API_KEY" in payload["data"]["error"]
    assert "api-key" not in str(payload).lower()
    assert payload["events"][0]["output"]["requested_tts_vendor"] == "xiaomi"
    assert payload["events"][0]["output"]["attempted_provider"] == "mimo_tts"


def test_volc_tts_provider_parses_success_response(monkeypatch):
    monkeypatch.setenv("VOLC_TTS_APP_ID", "tts-app")
    monkeypatch.setenv("VOLC_TTS_ACCESS_KEY", "tts-key")
    monkeypatch.setenv("VOLC_TTS_RESOURCE_ID", "seed-tts-1.0")

    class FakeResponse:
        text = '{"code":20000000,"data":"YQ=="}\n{"code":20000000,"data":"Yg=="}\n'

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers=None, json=None):
            assert url == VOLC_TTS_ENDPOINT
            assert headers["X-Api-App-Id"] == "tts-app"
            assert headers["X-Api-Access-Key"] == "tts-key"
            assert headers["X-Api-Resource-Id"] == "seed-tts-1.0"
            assert "X-Api-Request-Id" in headers
            assert json["req_params"]["speaker"] == "zh_female_wanwanxiaohe_moon_bigtts"
            assert json["req_params"]["text"] == "进入下一步。"
            return FakeResponse()

    monkeypatch.setattr("backend.speech.volc_tts.httpx.Client", FakeClient)

    result = VolcTTSProvider(get_settings()).synthesize("进入下一步。", "demo-kitchen-001")

    assert result.provider == "volc_tts"
    assert result.audio_base64 == "YWI="
    assert result.mime_type == "audio/mpeg"
