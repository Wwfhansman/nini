import asyncio
import time

from fastapi.testclient import TestClient

from backend.app import app
from backend.config import Settings
from backend.voice.session import VoiceWebSocketSession


TERMINAL_ID = "demo-kitchen-001"
PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"
VOICE_SAMPLE = int(1200).to_bytes(2, "little", signed=True)


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-voice-ws-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "mock")
    monkeypatch.setenv("VOICE_WAKE_WORDS", "妮妮,腻妮,nini")
    monkeypatch.setenv("VOICE_ACTIVE_IDLE_SECONDS", "25")
    monkeypatch.setenv("VOICE_SLEEP_SECONDS", "60")
    return TestClient(app)


def _control(client: TestClient, command: str):
    return client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": command})


def _chat(client: TestClient, text: str):
    return client.post("/api/chat", json={"terminal_id": TERMINAL_ID, "text": text, "source": "voice"})


def _prepare_cooking(client: TestClient) -> None:
    _control(client, "reset")
    _chat(client, PLAN_TEXT)
    _control(client, "start")


def _start_session(ws) -> list[dict]:
    ws.send_json({"type": "session.start", "terminal_id": TERMINAL_ID, "sample_rate": 16000})
    first = ws.receive_json()
    second = ws.receive_json()
    assert {first["type"], second["type"]} == {"asr.provider", "session.state"}
    state = first if first["type"] == "session.state" else second
    assert state["state"] == "listening_for_wake"
    return [first, second]


def _receive_until(ws, event_type: str, limit: int = 12) -> tuple[dict, list[dict]]:
    received = []
    for _ in range(limit):
        message = ws.receive_json()
        received.append(message)
        if message.get("type") == event_type:
            return message, received
    raise AssertionError(f"did not receive {event_type}; received={received}")


def test_voice_session_wake_word_stripping_next_step(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "妮妮，下一步"})

        response, messages = _receive_until(ws, "agent.response")

    assert any(message["type"] == "wake.detected" for message in messages)
    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["command"] == "next_step"
    assert response["state"]["current_step_index"] == 1


def test_voice_session_active_hao_le_routes_without_model(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "妮妮"})
        _receive_until(ws, "wake.detected")
        _receive_until(ws, "session.state")

        ws.send_json({"type": "asr.inject_final", "text": "好了"})
        response, _ = _receive_until(ws, "agent.response")

    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["command"] == "next_step"
    assert response["events"][0]["name"] == "next_step"


def test_voice_session_wake_vision_command_is_local(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "妮妮，看看食材"})
        response, _ = _receive_until(ws, "agent.response")

    assert response["state"]["ui_mode"] == "vision"
    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["intent"] == "start_vision"
    assert response["events"][0]["output"]["model_called"] is False


def test_voice_session_wake_free_cooking_control_routes_to_local_control(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "下一步"})
        response, messages = _receive_until(ws, "agent.response")

    assert any(message["type"] == "asr.final" and message["text"] == "下一步" for message in messages)
    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["command"] == "next_step"
    assert response["state"]["current_step_index"] == 1


def test_voice_session_no_wake_free_text_does_not_trigger_agent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "今天随便聊聊"})
        final, _ = _receive_until(ws, "asr.final")
        assert final["text"] == "今天随便聊聊"
        time.sleep(0.05)

    state_payload = client.get(f"/api/state?terminal_id={TERMINAL_ID}").json()["data"]
    event_names = [event["name"] for event in state_payload["tool_events"]]
    assert event_names.count("next_step") == 0


def test_voice_session_mock_connects_and_returns_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    with client.websocket_connect("/ws/voice") as ws:
        messages = _start_session(ws)

    provider = next(message for message in messages if message["type"] == "asr.provider")
    assert provider["provider"] == "mock_streaming_asr"


def test_voice_session_real_asr_waits_for_first_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-voice-ws-real-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "real")
    monkeypatch.setenv("VOLC_ASR_APP_KEY", "asr-app")
    monkeypatch.setenv("VOLC_ASR_ACCESS_KEY", "asr-key")
    monkeypatch.setenv("VOLC_ASR_RESOURCE_ID", "asr-resource")

    def fail_if_started(_settings):
        raise AssertionError("real ASR should not connect before the first audio chunk")

    monkeypatch.setattr("backend.voice.session.get_streaming_asr_provider", fail_if_started)
    client = TestClient(app)

    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "session.start", "terminal_id": TERMINAL_ID, "sample_rate": 16000})
        first = ws.receive_json()
        second = ws.receive_json()

    provider = first if first["type"] == "asr.provider" else second
    state = first if first["type"] == "session.state" else second
    assert provider["provider"] == "volc_streaming_asr"
    assert provider["message"] == "waiting_for_audio"
    assert state["state"] == "listening_for_wake"


def test_voice_session_audio_end_promotes_last_partial_to_final(tmp_path, monkeypatch):
    class PartialOnlySession:
        provider = "fake_streaming_asr"
        model = "fake-streaming-asr"
        fallback_used = False

        def __init__(self):
            self._queue = asyncio.Queue()
            self.closed = False
            self.finished = False

        async def send_audio(self, _chunk: bytes) -> None:
            await self._queue.put(
                {
                    "type": "partial",
                    "text": "妮妮，下一步",
                    "provider": self.provider,
                    "final": False,
                    "fallback_used": False,
                }
            )

        async def finish(self) -> None:
            self.finished = True

        async def close(self) -> None:
            self.closed = True

        async def receive_event(self, timeout=None):
            from backend.speech.streaming_asr import StreamingASREvent

            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
            return StreamingASREvent(**item)

    class PartialOnlyProvider:
        async def start_session(self, _terminal_id: str, _sample_rate: int = 16000):
            return PartialOnlySession()

    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-voice-ws-partial-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "real")
    monkeypatch.setenv("VOLC_ASR_APP_KEY", "asr-app")
    monkeypatch.setenv("VOLC_ASR_ACCESS_KEY", "asr-key")
    monkeypatch.setenv("VOLC_ASR_RESOURCE_ID", "asr-resource")
    monkeypatch.setattr("backend.voice.session.get_streaming_asr_provider", lambda _settings: PartialOnlyProvider())
    client = TestClient(app)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_bytes(VOICE_SAMPLE * 3200)
        partial, _ = _receive_until(ws, "asr.partial")
        assert partial["text"] == "妮妮，下一步"
        ws.send_json({"type": "audio.end"})
        response, messages = _receive_until(ws, "agent.response", limit=16)

    assert any(message["type"] == "asr.final" and message["text"] == "妮妮，下一步" for message in messages)
    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["command"] == "next_step"


def test_voice_session_mock_audio_emits_final_and_reaches_agent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_bytes(VOICE_SAMPLE * 9000)
        response, messages = _receive_until(ws, "agent.response")

    assert any(message["type"] == "asr.partial" for message in messages)
    assert any(message["type"] == "asr.final" and "妮妮" in message["text"] for message in messages)
    assert response["data"]["model_called"] is False
    assert response["data"]["voice_route"]["command"] == "next_step"
    assert response["state"]["current_step_index"] == 1


def test_voice_session_silent_pcm_does_not_trigger_mock_agent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_bytes(b"\x00\x00" * 24000)
        time.sleep(0.2)

    state_payload = client.get(f"/api/state?terminal_id={TERMINAL_ID}").json()["data"]
    assert state_payload["state"]["current_step_index"] == 0
    assert "next_step" not in [event["name"] for event in state_payload["tool_events"]]


def test_voice_session_mock_handles_two_utterances_in_same_socket(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_bytes(VOICE_SAMPLE * 9000)
        first_response, first_messages = _receive_until(ws, "agent.response")
        ws.send_bytes(VOICE_SAMPLE * 9000)
        second_response, second_messages = _receive_until(ws, "agent.response")

    assert any(message["type"] == "asr.final" for message in first_messages)
    assert any(message["type"] == "asr.final" for message in second_messages)
    assert first_response["state"]["current_step_index"] == 1
    assert second_response["state"]["current_step_index"] == 2


def test_voice_session_silent_audio_does_not_refresh_sleep_timer():
    class DummyWebSocket:
        async def send_json(self, _payload):
            return None

    class NoEventSession:
        provider = "fake_streaming_asr"
        model = "fake-streaming-asr"
        fallback_used = False

        def __init__(self):
            self.chunks = []

        async def send_audio(self, chunk: bytes) -> None:
            self.chunks.append(chunk)

        async def finish(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def receive_event(self, timeout=None):
            return None

    async def run_case():
        session = VoiceWebSocketSession(DummyWebSocket(), Settings())
        session.started = True
        session.asr_session = NoEventSession()
        session.last_activity_at = 123.0

        await session._handle_audio(b"\x00\x00" * 1600)
        assert session.last_activity_at == 123.0

        await session._handle_audio(VOICE_SAMPLE * 1600)
        assert session.last_activity_at > 123.0

    asyncio.run(run_case())


def test_voice_session_fallback_mock_does_not_emit_phantom_wake(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-voice-ws-fallback-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("SPEECH_PROVIDER_MODE", "real")
    monkeypatch.delenv("VOLC_ASR_APP_KEY", raising=False)
    monkeypatch.delenv("VOLC_ASR_ACCESS_KEY", raising=False)
    monkeypatch.delenv("VOLC_ASR_RESOURCE_ID", raising=False)
    client = TestClient(app)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "session.start", "terminal_id": TERMINAL_ID, "sample_rate": 16000})
        messages = [ws.receive_json(), ws.receive_json()]
        provider = next(message for message in messages if message["type"] == "asr.provider")
        assert provider["provider"] == "mock_streaming_asr"
        assert provider["fallback_used"] is True
        ws.send_bytes(VOICE_SAMPLE * 12000)
        ws.send_json({"type": "audio.end"})
        time.sleep(0.2)

    state_payload = client.get(f"/api/state?terminal_id={TERMINAL_ID}").json()["data"]
    assert state_payload["state"]["current_step_index"] == 0
    assert "next_step" not in [event["name"] for event in state_payload["tool_events"]]


def test_voice_session_agent_events_do_not_expose_internal_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _prepare_cooking(client)

    with client.websocket_connect("/ws/voice") as ws:
        _start_session(ws)
        ws.send_json({"type": "asr.inject_final", "text": "妮妮，下一步"})
        response, messages = _receive_until(ws, "agent.response")

    all_events = [message["event"] for message in messages if message["type"] == "agent.event"]
    all_events.extend(response["events"])
    assert all_events
    for event in all_events:
        assert "input_json" not in event
        assert "output_json" not in event
        assert "input" in event
        assert "output" in event
