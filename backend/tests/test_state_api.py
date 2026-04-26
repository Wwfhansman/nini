from fastapi.testclient import TestClient

from backend import database
from backend.app import app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def test_get_state_returns_default_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert payload["state"]["terminal_id"] == "demo-kitchen-001"


def test_start_enters_cooking(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "cooking"
    assert payload["state"]["timer_status"] == "running"
    assert payload["data"]["model_called"] is False


def test_next_step_updates_current_step_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["current_step_index"] == 1
    assert payload["state"]["ui_mode"] == "cooking"


def test_pause_resume_updates_timer_status(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    pause_response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "pause"})
    resume_response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "resume"})

    assert pause_response.status_code == 200
    assert resume_response.status_code == 200
    assert pause_response.json()["state"]["timer_status"] == "paused"
    assert resume_response.json()["state"]["timer_status"] == "running"


def test_finish_enters_review(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "review"
    assert payload["state"]["timer_status"] == "finished"


def test_tool_events_include_model_called_false(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    response = client.get("/api/state?terminal_id=demo-kitchen-001")

    assert response.status_code == 200
    events = response.json()["data"]["tool_events"]
    assert len(events) == 2
    assert all(event["event_type"] == "local_control" for event in events)
    assert all(event["output"]["model_called"] is False for event in events)
    assert all("output_json" not in event for event in events)


def test_reset_restores_default_planning_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert payload["state"]["current_step_index"] == 0
    assert payload["events"][0]["output"]["model_called"] is False
    assert "output_json" not in payload["events"][0]


def test_control_without_terminal_uses_configured_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "custom-kitchen")
    client = TestClient(app)

    control_response = client.post("/api/control", json={"command": "start"})
    state_response = client.get("/api/state")

    assert control_response.status_code == 200
    assert state_response.status_code == 200
    assert control_response.json()["state"]["terminal_id"] == "custom-kitchen"
    assert state_response.json()["state"]["terminal_id"] == "custom-kitchen"
    assert state_response.json()["state"]["ui_mode"] == "cooking"


def test_pause_resume_outside_active_cooking_do_not_create_invalid_timer_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    pause_before_start = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "pause"})
    resume_before_start = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "resume"})

    assert pause_before_start.status_code == 200
    assert resume_before_start.status_code == 200
    assert pause_before_start.json()["state"]["ui_mode"] == "planning"
    assert pause_before_start.json()["state"]["timer_status"] == "idle"
    assert resume_before_start.json()["state"]["ui_mode"] == "planning"
    assert resume_before_start.json()["state"]["timer_status"] == "idle"

    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})
    resume_after_finish = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "resume"})

    assert resume_after_finish.status_code == 200
    assert resume_after_finish.json()["state"]["ui_mode"] == "review"
    assert resume_after_finish.json()["state"]["timer_status"] == "finished"


def test_list_tool_events_returns_recent_events_when_limited(tmp_path, monkeypatch):
    db_path = str(tmp_path / "nini-test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    terminal_id = "demo-kitchen-001"
    database.init_db(db_path)

    for index in range(105):
        database.add_tool_event(
            terminal_id=terminal_id,
            event_type="local_control",
            name=f"event_{index:03d}",
            output_json={"model_called": False, "index": index},
            db_path=db_path,
        )

    events = database.list_tool_events(terminal_id, limit=100, db_path=db_path)

    assert len(events) == 100
    assert events[0]["name"] == "event_005"
    assert events[-1]["name"] == "event_104"
