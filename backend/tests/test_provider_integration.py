import json

from fastapi.testclient import TestClient

from backend.agent import runtime
from backend.agent.providers import QiniuChatProvider, QiniuVisionProvider, normalize_agent_output_payload
from backend.app import app
from backend.config import get_settings


PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"


def _client(
    tmp_path,
    monkeypatch,
    *,
    mode: str = "mock",
    qiniu_key: str = "",
    model_agent: str = "",
    model_vision: str = "",
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-provider-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", mode)
    if qiniu_key:
        monkeypatch.setenv("QINIU_API_KEY", qiniu_key)
    else:
        monkeypatch.delenv("QINIU_API_KEY", raising=False)
    if model_agent:
        monkeypatch.setenv("MODEL_AGENT", model_agent)
    else:
        monkeypatch.delenv("MODEL_AGENT", raising=False)
    if model_vision:
        monkeypatch.setenv("MODEL_VISION", model_vision)
    else:
        monkeypatch.delenv("MODEL_VISION", raising=False)
    return TestClient(app)


def test_settings_read_provider_environment(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "hybrid")
    monkeypatch.setenv("QINIU_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("QINIU_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_AGENT", "agent-model")
    monkeypatch.setenv("MODEL_VISION", "vision-model")
    monkeypatch.setenv("MODEL_FAST_CHAT", "fast-model")
    monkeypatch.setenv("MODEL_AGENT_THINKING", "thinking-model")
    monkeypatch.setenv("PROVIDER_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("ENABLE_PROVIDER_LOGS", "false")
    monkeypatch.setenv("VOLC_TTS_APP_ID", "tts-app")
    monkeypatch.setenv("VOLC_TTS_ACCESS_KEY", "tts-token")
    monkeypatch.setenv("VOLC_TTS_RESOURCE_ID", "seed-tts-1.0")
    monkeypatch.setenv("VOLC_ASR_APP_KEY", "asr-app")
    monkeypatch.setenv("VOLC_ASR_ACCESS_KEY", "asr-key")
    monkeypatch.setenv("VOLC_ASR_RESOURCE_ID", "asr-resource")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "auto")
    monkeypatch.setenv("SPEECH_TIMEOUT_SECONDS", "9")

    settings = get_settings()

    assert settings.demo_mode == "hybrid"
    assert settings.qiniu_base_url == "https://example.test/v1"
    assert settings.qiniu_configured is True
    assert settings.model_agent == "agent-model"
    assert settings.model_vision == "vision-model"
    assert settings.model_fast_chat == "fast-model"
    assert settings.model_agent_thinking == "thinking-model"
    assert settings.provider_timeout_seconds == 12.5
    assert settings.enable_provider_logs is False
    assert settings.volc_tts_configured is True
    assert settings.volc_asr_configured is True
    assert settings.speech_provider_mode == "auto"
    assert settings.speech_timeout_seconds == 9

    monkeypatch.setenv("DEMO_MODE", "unknown")
    assert get_settings().demo_mode == "mock"
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "unknown")
    assert get_settings().speech_provider_mode == "mock"


def test_hybrid_chat_missing_key_falls_back_to_mock_and_logs_error(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, mode="hybrid")

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["data"]["provider"]["name"] == "qiniu_chat"
    assert payload["data"]["provider"]["fallback_used"] is True
    assert "QINIU_API_KEY" in payload["data"]["provider"]["error"]
    assert payload["events"][0]["name"] == "provider_error"
    assert payload["events"][0]["status"] == "fallback"
    assert "QINIU_API_KEY" in payload["events"][0]["output"]["error"]
    assert "recipe_plan" in [event["name"] for event in payload["events"]]

    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    provider_logs = state_payload["provider_logs"]
    assert provider_logs[-1]["provider"] == "qiniu_chat"
    assert provider_logs[-1]["status"] == "error"
    assert "QINIU_API_KEY" in provider_logs[-1]["error"]


def test_qiniu_chat_invalid_json_falls_back_without_state_break(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        mode="hybrid",
        qiniu_key="test-key",
        model_agent="agent-model",
    )

    def fake_post_chat(self, payload):
        return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(QiniuChatProvider, "_post_chat", fake_post_chat)

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["data"]["provider"]["fallback_used"] is True
    assert "invalid AgentOutput JSON" in payload["data"]["provider"]["error"]
    assert payload["events"][0]["name"] == "provider_error"
    assert payload["events"][0]["input"]["model"] == "agent-model"
    assert "test-key" not in response.text


def test_qiniu_chat_normalizes_common_memory_aliases(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        mode="hybrid",
        qiniu_key="test-key",
        model_agent="agent-model",
    )

    def fake_post_chat(self, payload):
        content = {
            "intent": "plan_recipe",
            "ui_mode": "planning",
            "speech": "我建议做低脂不辣番茄鸡胸肉滑蛋。",
            "ui_patch": {},
            "tool_calls": [{"name": "recipe_plan"}],
            "memory_writes": [
                {"type": "dietary_goal", "key": "dietary_goal", "content": "减脂"},
                {"memory_type": "food_restriction", "person": "妈妈", "content": "不吃辣"},
            ],
            "inventory_patches": [],
            "recipe_adjustments": [],
        }
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}

    monkeypatch.setattr(QiniuChatProvider, "_post_chat", fake_post_chat)

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"]["fallback_used"] is False
    assert payload["events"][0]["name"] == "provider_call"
    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    memories = {(memory["subject"], memory["key"]): memory for memory in state_payload["memories"]}
    assert memories[("user", "health_goal.diet")]["type"] == "health_goal"
    assert memories[("user", "health_goal.diet")]["value_json"]["text"] == "减脂"
    assert memories[("mother", "diet.spicy")]["type"] == "allergy_or_restriction"
    assert memories[("mother", "diet.spicy")]["value_json"]["text"] == "不吃辣"
    export = client.get("/api/export/memory?terminal_id=demo-kitchen-001")
    assert export.status_code == 200
    assert "用户最近在减脂" in export.text
    assert "妈妈不吃辣" in export.text


def test_normalize_agent_output_payload_fills_missing_memory_fields():
    payload = {
        "intent": "remember",
        "ui_mode": "cooking",
        "speech": "记住了。",
        "memory_writes": [
            {"content": "用户不喜欢太酸"},
            {"type": "food_restriction", "target": "mom", "value": "不吃辣"},
        ],
    }

    normalized = normalize_agent_output_payload(payload)

    assert normalized["tool_calls"] == []
    assert normalized["memory_writes"][0] == {
        "type": "preference",
        "subject": "user",
        "key": "taste.sour",
        "value": "用户不喜欢太酸",
        "confidence": 0.9,
        "source": "user_explicit",
    }
    assert normalized["memory_writes"][1]["type"] == "allergy_or_restriction"
    assert normalized["memory_writes"][1]["subject"] == "mother"
    assert normalized["memory_writes"][1]["key"] == "diet.spicy"


def test_p0_chat_control_does_not_resolve_provider(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, mode="real")
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})

    def fail_if_called(settings):
        raise AssertionError("P0 control should not resolve a provider")

    monkeypatch.setattr(runtime, "get_agent_provider", fail_if_called)

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "开始做。", "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "cooking"
    assert payload["data"]["model_called"] is False
    assert payload["events"][0]["event_type"] == "local_control"
    assert payload["events"][0]["name"] == "start"


def test_real_vision_missing_key_falls_back_to_mock(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, mode="real", model_vision="vision-model")

    response = client.post(
        "/api/vision",
        data={"terminal_id": "demo-kitchen-001", "purpose": "ingredients"},
        files={"image": ("ingredients.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"]["name"] == "qiniu_vision"
    assert payload["data"]["provider"]["fallback_used"] is True
    assert payload["data"]["observation"]["ingredients"][0]["name"] == "番茄"
    assert payload["events"][0]["name"] == "vision_provider_fallback"
    assert payload["events"][0]["status"] == "fallback"
    assert "QINIU_API_KEY" in payload["events"][0]["output"]["error"]
    assert [event["name"] for event in payload["events"][-3:]] == [
        "vision_observe",
        "inventory_update",
        "recipe_adjust",
    ]

    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    provider_logs = state_payload["provider_logs"]
    assert provider_logs[-1]["provider"] == "qiniu_vision"
    assert provider_logs[-1]["status"] == "error"


def test_real_vision_speech_matches_non_tomato_observation(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        mode="real",
        qiniu_key="test-key",
        model_vision="vision-model",
    )

    def fake_post_chat(self, payload):
        content = {
            "scene": "kitchen_counter",
            "ingredients": [
                {"name": "鸡蛋", "amount": "2个", "confidence": 0.95},
                {"name": "青菜", "amount": "一把", "confidence": 0.9},
            ],
            "notes": ["未看到番茄"],
        }
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}

    monkeypatch.setattr(QiniuVisionProvider, "_post_chat", fake_post_chat)

    response = client.post(
        "/api/vision",
        data={"terminal_id": "demo-kitchen-001", "purpose": "ingredients"},
        files={"image": ("ingredients.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    speech = payload["data"]["speech"]
    assert payload["data"]["provider"]["name"] == "qiniu_vision"
    assert payload["data"]["provider"]["fallback_used"] is False
    assert payload["events"][0]["name"] == "provider_call"
    assert payload["events"][1]["name"] == "vision_observe"
    assert "鸡蛋2个" in speech
    assert "青菜一把" in speech
    assert "番茄只有半个" not in speech
    assert "一人份" not in speech
    assert payload["state"]["last_speech"] == speech
    assert payload["state"]["recipe"]["servings"] == "1-2人份"
