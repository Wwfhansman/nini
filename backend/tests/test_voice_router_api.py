from fastapi.testclient import TestClient

from backend.app import app


TERMINAL_ID = "demo-kitchen-001"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def _control(client: TestClient, command: str):
    return client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": command})


def _chat(client: TestClient, text: str):
    return client.post("/api/chat", json={"terminal_id": TERMINAL_ID, "text": text, "source": "voice"})


def test_wake_word_next_step_routes_to_local_control_without_provider(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")
    _control(client, "start")

    response = _chat(client, "妮妮，下一步。")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["voice_route"]["route"] == "local_control"
    assert payload["data"]["voice_route"]["command"] == "next_step"
    assert payload["events"][0]["event_type"] == "local_control"
    assert payload["events"][0]["name"] == "next_step"
    assert payload["state"]["current_step_index"] == 1
    assert not any(event["name"] == "provider_call" for event in payload["events"])


def test_cooking_hao_le_routes_to_next_step(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")
    _control(client, "start")

    response = _chat(client, "好了。")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["events"][0]["name"] == "next_step"
    assert payload["state"]["current_step_index"] == 1


def test_voice_pause_and_resume_update_timer_status(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")
    _control(client, "start")

    pause = _chat(client, "等一下")
    resume = _chat(client, "我回来了")

    assert pause.status_code == 200
    assert resume.status_code == 200
    assert pause.json()["events"][0]["name"] == "pause"
    assert pause.json()["state"]["timer_status"] == "paused"
    assert resume.json()["events"][0]["name"] == "resume"
    assert resume.json()["state"]["timer_status"] == "running"
    assert pause.json()["data"]["model_called"] is False
    assert resume.json()["data"]["model_called"] is False


def test_repeat_current_step_does_not_change_step_and_speaks_instruction(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")
    _control(client, "start")
    before = client.get(f"/api/state?terminal_id={TERMINAL_ID}").json()["state"]

    response = _chat(client, "这一步再说一遍")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["events"][0]["name"] == "repeat_current_step"
    assert payload["state"]["current_step_index"] == before["current_step_index"]
    assert payload["state"]["ui_mode"] == before["ui_mode"]
    assert payload["state"]["timer_status"] == before["timer_status"]
    assert "鸡胸肉切薄片并轻腌" in payload["data"]["speech"]
    assert "把鸡胸肉切成薄片" in payload["data"]["speech"]


def test_planning_confirmation_starts_cooking(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")

    response = _chat(client, "就做这个")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["voice_route"]["command"] == "start"
    assert payload["state"]["ui_mode"] == "cooking"


def test_planning_hao_le_starts_cooking(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")

    response = _chat(client, "好了。")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["voice_route"]["command"] == "start"
    assert payload["state"]["ui_mode"] == "cooking"


def test_repeat_prompt_in_planning_stays_on_agent_path(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")

    response = _chat(client, "这一步怎么做")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["intent"] == "small_reply"
    assert "voice_route" not in payload["data"]
    assert not any(event["event_type"] == "local_control" for event in payload["events"])


def test_repeat_prompt_in_review_stays_on_agent_path(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")
    _control(client, "start")
    _control(client, "finish")

    response = _chat(client, "这一步怎么做")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["intent"] == "small_reply"
    assert payload["state"]["ui_mode"] == "review"
    assert not any(event["event_type"] == "local_control" for event in payload["events"])


def test_complex_voice_request_stays_on_agent_path(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _control(client, "reset")

    response = _chat(client, "妈妈今天也吃，别放辣")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["intent"] == "small_reply"
    assert "voice_route" not in payload["data"]
    assert not any(event["event_type"] == "local_control" for event in payload["events"])
