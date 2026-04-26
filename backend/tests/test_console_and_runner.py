from fastapi.testclient import TestClient

from backend.app import app
from scripts import run_mock_demo as runner
from scripts.run_mock_demo import (
    StepResult,
    demo_failed,
    p0_model_called_false,
    successful_real_provider_call,
    validate_demo_summary,
)


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def test_test_console_is_accessible(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/test-console")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "妮妮 Kitchen Agent Test Console" in response.text
    assert "一键演示流程" in response.text
    assert "/api/chat" in response.text
    assert "/api/vision" in response.text
    assert "/api/speech/tts" in response.text
    assert "/api/speech/asr" in response.text
    assert "DEMO_MODE" in response.text
    assert "provider_logs" in response.text


def test_static_test_console_is_accessible(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/static/test-console.html")

    assert response.status_code == 200
    assert "tool_events" in response.text
    assert "provider_logs" in response.text
    assert "语音调试" in response.text


def test_export_memory_empty_card_is_markdown(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})

    response = client.get("/api/export/memory?terminal_id=demo-kitchen-001")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# 张家厨房记忆卡" in response.text


def test_demo_runner_validation_accepts_expected_summary():
    summary = {
        "plan": {"state": {"ui_mode": "planning"}, "events": [{"name": "recipe_plan"}]},
        "vision": {
            "state": {"ui_mode": "vision"},
            "events": [
                {"name": "vision_observe"},
                {"name": "inventory_update"},
                {"name": "recipe_adjust"},
            ],
        },
        "start": {"state": {"ui_mode": "cooking"}, "events": [{"name": "start"}]},
        "sour_memory": {"state": {"ui_mode": "cooking"}, "events": [{"name": "memory_write"}]},
        "next_step": {
            "state": {"ui_mode": "cooking"},
            "events": [
                {
                    "event_type": "local_control",
                    "name": "next_step",
                    "output": {"model_called": False},
                }
            ],
        },
        "finish": {"state": {"ui_mode": "review"}, "events": [{"name": "finish"}]},
        "memory_markdown": "# 张家厨房记忆卡\n\n- 用户不喜欢太酸\n",
    }

    assert validate_demo_summary(summary) == []
    assert p0_model_called_false(summary["next_step"]) is True


def test_demo_runner_validation_reports_failures():
    summary = {
        "plan": {"state": {"ui_mode": "cooking"}, "events": []},
        "vision": {"state": {"ui_mode": "vision"}, "events": []},
        "start": {"state": {"ui_mode": "planning"}, "events": []},
        "sour_memory": {"state": {"ui_mode": "planning"}, "events": []},
        "next_step": {"state": {"ui_mode": "cooking"}, "events": []},
        "finish": {"state": {"ui_mode": "cooking"}, "events": []},
        "memory_markdown": "# 张家厨房记忆卡\n",
    }

    failures = validate_demo_summary(summary)

    assert "initial planning did not end in ui_mode=planning" in failures
    assert "next_step did not record model_called=false" in failures
    assert "memory export does not contain sour preference" in failures


def test_demo_runner_requires_sour_preference_in_memory_export():
    summary = {
        "plan": {"state": {"ui_mode": "planning"}, "events": [{"name": "recipe_plan"}]},
        "vision": {
            "state": {"ui_mode": "vision"},
            "events": [
                {"name": "vision_observe"},
                {"name": "inventory_update"},
                {"name": "recipe_adjust"},
            ],
        },
        "start": {"state": {"ui_mode": "cooking"}, "events": [{"name": "start"}]},
        "sour_memory": {"state": {"ui_mode": "cooking"}, "events": [{"name": "memory_write"}]},
        "next_step": {
            "state": {"ui_mode": "cooking"},
            "events": [
                {
                    "event_type": "local_control",
                    "name": "next_step",
                    "output": {"model_called": False},
                }
            ],
        },
        "finish": {"state": {"ui_mode": "review"}, "events": [{"name": "finish"}]},
        "memory_markdown": "# 张家厨房记忆卡\n\n- 妈妈不吃辣\n",
    }

    assert validate_demo_summary(summary) == ["memory export does not contain sour preference"]


def test_demo_runner_fails_when_any_step_assertion_fails():
    step_results = [
        StepResult(
            name="control pause",
            status_code=200,
            ui_mode="cooking",
            events=["pause"],
            passed=False,
            message="expect model_called=false",
        )
    ]

    assert demo_failed(step_results, summary_failures=[]) is True
    assert demo_failed([], summary_failures=["missing event"]) is True
    assert demo_failed(
        [
            StepResult(
                name="control pause",
                status_code=200,
                ui_mode="cooking",
                events=["pause"],
                passed=True,
                message="expect model_called=false",
            )
        ],
        summary_failures=[],
    ) is False


def test_hybrid_smoke_skips_chat_when_backend_provider_not_configured(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def get(self, url, params=None):
            if url.endswith("/health"):
                return FakeResponse(
                    {
                        "demo_mode": "hybrid",
                        "providers": {
                            "qiniu_configured": False,
                            "agent_model_configured": False,
                        },
                    }
                )
            if url.endswith("/api/state"):
                return FakeResponse({"state": {"ui_mode": "planning"}})
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, json=None):
            raise AssertionError("chat should be skipped when backend provider is not configured")

    monkeypatch.setattr(runner.httpx, "Client", FakeClient)

    assert runner.run_hybrid_smoke("http://backend.test", "demo-kitchen-001") == 0


def test_hybrid_smoke_fails_when_chat_uses_provider_fallback(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def get(self, url, params=None):
            if url.endswith("/health"):
                return FakeResponse(
                    {
                        "demo_mode": "hybrid",
                        "providers": {
                            "qiniu_configured": True,
                            "agent_model_configured": True,
                        },
                    }
                )
            if url.endswith("/api/state"):
                return FakeResponse({"state": {"ui_mode": "planning"}})
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, json=None):
            if url.endswith("/api/chat"):
                return FakeResponse(
                    {
                        "state": {"ui_mode": "planning"},
                        "data": {
                            "provider": {
                                "name": "qiniu_chat",
                                "fallback_used": True,
                            }
                        },
                        "events": [{"name": "provider_error"}],
                    }
                )
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(runner.httpx, "Client", FakeClient)

    assert runner.run_hybrid_smoke("http://backend.test", "demo-kitchen-001") == 1


def test_successful_real_provider_call_requires_provider_call_event():
    success_payload = {
        "data": {"provider": {"name": "qiniu_chat", "fallback_used": False}},
        "events": [{"name": "provider_call", "output": {"status": "success"}}],
    }
    fallback_payload = {
        "data": {"provider": {"name": "qiniu_chat", "fallback_used": True}},
        "events": [{"name": "provider_error", "output": {"status": "fallback_to_mock"}}],
    }
    mock_payload = {
        "data": {"provider": {"name": "mock_agent", "fallback_used": False}},
        "events": [],
    }

    assert successful_real_provider_call(success_payload) is True
    assert successful_real_provider_call(fallback_payload) is False
    assert successful_real_provider_call(mock_payload) is False


def test_speech_smoke_accepts_mock_speech(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def get(self, url, params=None):
            if url.endswith("/health"):
                return FakeResponse(
                    {
                        "providers": {
                            "speech_provider_mode": "mock",
                            "volc_tts_configured": False,
                            "volc_asr_configured": False,
                        }
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, json=None, data=None, files=None):
            if url.endswith("/api/speech/tts"):
                return FakeResponse({"data": {"provider": "mock_tts", "fallback_used": False, "audio_base64": ""}})
            if url.endswith("/api/speech/asr"):
                return FakeResponse({"data": {"provider": "mock_asr", "fallback_used": False, "text": "下一步"}})
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(runner.httpx, "Client", FakeClient)

    assert runner.run_speech_smoke("http://backend.test", "demo-kitchen-001") == 0


def test_speech_smoke_fails_when_configured_tts_falls_back(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def get(self, url, params=None):
            if url.endswith("/health"):
                return FakeResponse(
                    {
                        "providers": {
                            "speech_provider_mode": "real",
                            "volc_tts_configured": True,
                            "volc_asr_configured": False,
                        }
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, json=None, data=None, files=None):
            if url.endswith("/api/speech/tts"):
                return FakeResponse({"data": {"provider": "mock_tts", "fallback_used": True, "error": "failed"}})
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(runner.httpx, "Client", FakeClient)

    assert runner.run_speech_smoke("http://backend.test", "demo-kitchen-001") == 1
