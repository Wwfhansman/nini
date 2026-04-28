from fastapi.testclient import TestClient

from backend import database
from backend.app import app


PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def _plan(client: TestClient, terminal_id: str = "demo-kitchen-001"):
    return client.post("/api/chat", json={"terminal_id": terminal_id, "text": PLAN_TEXT, "source": "text"})


def test_get_state_returns_default_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert payload["state"]["terminal_id"] == "demo-kitchen-001"
    assert payload["state"]["recipe"] is None
    assert payload["state"]["dish_name"] is None


def test_start_without_recipe_stays_planning_with_friendly_speech(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert "请先规划" in payload["data"]["speech"]
    assert payload["data"]["model_called"] is False


def test_start_enters_cooking_after_planning(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "cooking"
    assert payload["state"]["timer_status"] == "running"
    assert payload["data"]["model_called"] is False


def test_next_step_updates_current_step_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["current_step_index"] == 1
    assert payload["state"]["ui_mode"] == "cooking"


def test_pause_resume_updates_timer_status(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    pause_response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "pause"})
    resume_response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "resume"})

    assert pause_response.status_code == 200
    assert resume_response.status_code == 200
    assert pause_response.json()["state"]["timer_status"] == "paused"
    assert resume_response.json()["state"]["timer_status"] == "running"


def test_finish_enters_review(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "review"
    assert payload["state"]["timer_status"] == "finished"


def test_finish_without_recipe_stays_planning_with_friendly_speech(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert "请先规划" in payload["data"]["speech"]
    assert not payload["state"].get("review")


def test_finish_preserves_inventory_metadata_when_marking_used(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    db_path = str(tmp_path / "nini-test.db")
    _plan(client)
    database.upsert_inventory_item(
        terminal_id="demo-kitchen-001",
        name="鸡蛋",
        amount="2",
        unit="个",
        category="蛋类",
        freshness="新鲜",
        source="test",
        db_path=db_path,
    )
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert response.status_code == 200
    payload = response.json()
    egg_change = next(item for item in payload["state"]["review"]["inventory_changes"] if item["name"] == "鸡蛋")
    assert egg_change["before"] == "2"
    assert egg_change["unit"] == "个"
    assert egg_change["freshness"] == "新鲜"
    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    egg_item = next(item for item in state_payload["inventory"] if item["name"] == "鸡蛋")
    assert egg_item["unit"] == "个"
    assert egg_item["freshness"] == "新鲜"


def test_repeated_finish_does_not_emit_duplicate_review_events(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    first = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    second = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert {"inventory_deduct", "cooking_review"}.issubset(
        {event["name"] for event in first.json()["events"]}
    )
    assert "inventory_deduct" not in {event["name"] for event in second.json()["events"]}
    assert "cooking_review" not in {event["name"] for event in second.json()["events"]}
    assert second.json()["state"]["ui_mode"] == "review"


def test_tool_events_include_model_called_false(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    response = client.get("/api/state?terminal_id=demo-kitchen-001")

    assert response.status_code == 200
    events = [
        event
        for event in response.json()["data"]["tool_events"]
        if event["name"] in {"start", "next_step"}
    ]
    assert len(events) == 2
    assert all(event["event_type"] == "local_control" for event in events)
    assert all(event["output"]["model_called"] is False for event in events)
    assert all("output_json" not in event for event in events)


def test_reset_restores_default_planning_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _plan(client)
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["timer_status"] == "idle"
    assert payload["state"]["current_step_index"] == 0
    assert payload["state"]["recipe"] is None
    assert payload["events"][0]["output"]["model_called"] is False
    assert "output_json" not in payload["events"][0]


def test_control_without_terminal_uses_configured_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "custom-kitchen")
    client = TestClient(app)

    client.post("/api/chat", json={"text": PLAN_TEXT, "source": "text"})
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

    _plan(client)
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
