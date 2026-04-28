from fastapi.testclient import TestClient

from backend.app import app


TERMINAL_ID = "demo-kitchen-001"
PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def _chat(client: TestClient, text: str):
    return client.post("/api/chat", json={"terminal_id": TERMINAL_ID, "text": text, "source": "voice"})


def _reset(client: TestClient):
    return client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": "reset"})


def _state_data(client: TestClient):
    return client.get(f"/api/state?terminal_id={TERMINAL_ID}").json()["data"]


def _memory_texts(client: TestClient):
    return [memory["value_json"]["text"] for memory in _state_data(client)["memories"]]


def _plan(client: TestClient):
    return _chat(client, PLAN_TEXT)


def _make_delete_pending(client: TestClient):
    _reset(client)
    _plan(client)
    return _chat(client, "不要记妈妈不吃辣了")


def test_memory_delete_requires_confirmation(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = _make_delete_pending(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["memory_action"]["type"] == "delete_pending"
    assert payload["state"]["pending_action"]["type"] == "delete_memory"
    assert "妈妈不吃辣" in payload["state"]["pending_action"]["summary"]
    assert "不吃辣" in _memory_texts(client)
    assert payload["events"][0]["name"] == "memory_delete_pending"
    assert payload["events"][0]["output"]["model_called"] is False


def test_memory_delete_confirm_removes_memory(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _make_delete_pending(client)

    response = _chat(client, "确认")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["memory_action"]["type"] == "deleted"
    assert not payload["state"].get("pending_action")
    assert "不吃辣" not in _memory_texts(client)
    assert payload["events"][0]["name"] == "memory_delete"


def test_memory_delete_cancel_keeps_memory(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _make_delete_pending(client)

    response = _chat(client, "算了")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["memory_action"]["type"] == "cancel"
    assert not payload["state"].get("pending_action")
    assert "不吃辣" in _memory_texts(client)
    assert payload["events"][0]["name"] == "memory_delete_cancel"


def test_recent_memory_correction_targets_latest_memory(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    _plan(client)
    _chat(client, "记住我不喜欢太酸")
    sour_memory = next(
        memory for memory in _state_data(client)["memories"] if memory["key"] == "taste.sour"
    )

    response = _chat(client, "刚才那个记错了")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["memory_action"]["type"] == "delete_pending"
    assert payload["state"]["pending_action"]["memory_id"] == sour_memory["id"]
    assert "不喜欢太酸" in payload["state"]["pending_action"]["summary"]
    assert "不喜欢太酸" in _memory_texts(client)


def test_memory_delete_request_matches_sour_preference(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    _plan(client)
    _chat(client, "记住我不喜欢太酸")
    sour_memory = next(
        memory for memory in _state_data(client)["memories"] if memory["key"] == "taste.sour"
    )

    response = _chat(client, "不要记我不喜欢太酸了")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["memory_action"]["type"] == "delete_pending"
    assert payload["state"]["pending_action"]["memory_id"] == sour_memory["id"]
    assert "不喜欢太酸" in payload["state"]["pending_action"]["summary"]


def test_plain_sour_preference_does_not_trigger_memory_delete(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)

    response = _chat(client, "不要太酸")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["intent"] == "small_reply"
    assert "memory_action" not in payload["data"]
    assert not any(event["name"] == "memory_delete_pending" for event in payload["events"])


def test_confirm_without_pending_is_local_noop(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)

    response = _chat(client, "确认")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["model_called"] is False
    assert payload["data"]["memory_action"]["type"] == "not_found"
    assert not payload["state"].get("pending_action")
    assert payload["events"][0]["name"] == "memory_delete_not_found"


def test_unrelated_chat_clears_stale_delete_confirmation(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _make_delete_pending(client)

    unrelated = _chat(client, "下次做番茄类菜要注意什么？")
    confirm = _chat(client, "确认")

    assert unrelated.status_code == 200
    assert not unrelated.json()["state"].get("pending_action")
    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload["data"]["memory_action"]["type"] == "not_found"
    assert "不吃辣" in _memory_texts(client)
    assert confirm_payload["events"][0]["name"] == "memory_delete_not_found"


def test_control_clears_stale_delete_confirmation(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _make_delete_pending(client)

    control = client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": "start"})
    confirm = _chat(client, "确认")

    assert control.status_code == 200
    assert not control.json()["state"].get("pending_action")
    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload["data"]["memory_action"]["type"] == "not_found"
    assert "不吃辣" in _memory_texts(client)


def test_unmatched_delete_request_clears_previous_pending(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _make_delete_pending(client)

    missing = _chat(client, "不要记爸爸不吃香菜了")
    confirm = _chat(client, "确认")

    assert missing.status_code == 200
    missing_payload = missing.json()
    assert missing_payload["data"]["memory_action"]["type"] == "not_found"
    assert not missing_payload["state"].get("pending_action")
    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload["data"]["memory_action"]["type"] == "not_found"
    assert "不吃辣" in _memory_texts(client)
