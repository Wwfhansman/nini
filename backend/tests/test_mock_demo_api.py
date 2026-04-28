from fastapi.testclient import TestClient

from backend.app import app


PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def _reset(client: TestClient):
    return client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})


def test_chat_initial_plan_writes_memory_inventory_and_planning_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["intent"] == "plan_recipe"
    assert payload["state"]["ui_mode"] == "planning"
    assert payload["state"]["dish_name"] == "低脂不辣番茄鸡胸肉滑蛋"
    assert "少油/低脂" in payload["state"]["active_adjustments"]
    assert "不放辣" in payload["state"]["active_adjustments"]
    assert [event["name"] for event in payload["events"]] == [
        "memory_write",
        "inventory_update",
        "recipe_plan",
    ]
    assert all("output_json" not in event for event in payload["events"])

    state_response = client.get("/api/state?terminal_id=demo-kitchen-001")
    state_payload = state_response.json()["data"]
    memory_values = [memory["value_json"]["text"] for memory in state_payload["memories"]]
    memory_sources = [memory["source"] for memory in state_payload["memories"]]
    inventory_names = [item["name"] for item in state_payload["inventory"]]
    assert "减脂" in memory_values
    assert "不吃辣" in memory_values
    assert set(memory_sources) == {"user_explicit"}
    assert {"鸡胸肉", "番茄", "鸡蛋"}.issubset(set(inventory_names))
    assert {"memory_write", "inventory_update", "recipe_plan"}.issubset(
        {event["name"] for event in state_payload["tool_events"]}
    )


def test_vision_returns_mock_observation_and_adjusts_recipe(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})

    response = client.post(
        "/api/vision",
        data={"terminal_id": "demo-kitchen-001", "purpose": "ingredients"},
        files={"image": ("ingredients.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["observation"]["ingredients"][0]["name"] == "番茄"
    assert payload["data"]["observation"]["ingredients"][0]["amount"] == "半个"
    assert payload["state"]["ui_mode"] == "vision"
    assert payload["state"]["recipe"]["servings"] == "1人份"
    assert "降低酸度" in payload["state"]["active_adjustments"]
    assert [event["name"] for event in payload["events"]] == [
        "vision_observe",
        "inventory_update",
        "recipe_adjust",
    ]


def test_chat_p0_with_sentence_punctuation_routes_to_local_control(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})

    start = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "开始做。", "source": "text"},
    )
    next_step = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "下一步。", "source": "text"},
    )

    assert start.status_code == 200
    assert next_step.status_code == 200
    start_payload = start.json()
    next_payload = next_step.json()
    assert start_payload["state"]["ui_mode"] == "cooking"
    assert start_payload["data"]["model_called"] is False
    assert start_payload["events"][0]["event_type"] == "local_control"
    assert start_payload["events"][0]["name"] == "start"
    assert next_payload["state"]["current_step_index"] == 1
    assert next_payload["data"]["model_called"] is False
    assert next_payload["events"][0]["event_type"] == "local_control"
    assert next_payload["events"][0]["name"] == "next_step"


def test_chat_sour_memory_keeps_cooking_and_writes_memory(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "记住我不喜欢太酸", "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "cooking"
    assert "用户不喜欢太酸" in payload["state"]["active_adjustments"]
    assert [event["name"] for event in payload["events"]] == ["memory_write", "recipe_adjust"]

    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    memory_values = [memory["value_json"]["text"] for memory in state_payload["memories"]]
    assert "不喜欢太酸" in memory_values


def test_export_memory_markdown_contains_saved_preferences(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "记住我不喜欢太酸", "source": "text"},
    )

    response = client.get("/api/export/memory?terminal_id=demo-kitchen-001")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# 张家厨房记忆卡" in response.text
    assert "用户不喜欢太酸" in response.text
    assert "妈妈不吃辣" in response.text


def test_recipe_knowledge_import_records_document_and_event(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)

    response = client.post(
        "/api/knowledge/recipe",
        json={
            "terminal_id": "demo-kitchen-001",
            "title": "妈妈版番茄炒蛋",
            "content": "不放辣，鸡蛋多一点，出锅前加一点糖。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["document_id"].startswith("recipe_doc_")
    assert payload["events"][0]["name"] == "recipe_knowledge_import"
    state_payload = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]
    assert state_payload["recipe_documents"][0]["title"] == "妈妈版番茄炒蛋"


def test_recipe_knowledge_influences_next_plan(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post(
        "/api/knowledge/recipe",
        json={
            "terminal_id": "demo-kitchen-001",
            "title": "妈妈版番茄炒蛋",
            "content": "妈妈版番茄炒蛋会多放鸡蛋，不放辣，番茄少炒。",
        },
    )

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "参考家庭菜谱" in payload["state"]["active_adjustments"]
    assert "家庭菜谱" in payload["state"]["recipe"]["reasoning_summary"]


def test_finish_generates_review_and_inventory_deduction(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})

    response = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["ui_mode"] == "review"
    assert payload["state"]["review"]["inventory_changes"]
    assert {"鸡胸肉", "番茄", "鸡蛋"}.issubset(
        {item["name"] for item in payload["state"]["review"]["inventory_changes"]}
    )
    assert {"inventory_deduct", "cooking_review"}.issubset(
        {event["name"] for event in payload["events"]}
    )
    assert all("已使用" in item["after"] for item in payload["state"]["review"]["inventory_changes"])


def test_chat_tomato_followup_uses_mock_memory_answer(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "记住我不喜欢太酸", "source": "text"},
    )

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "下次做番茄类菜要注意什么？", "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["intent"] == "answer_tomato_memory"
    assert "默认降低酸度" in payload["data"]["speech"]


def test_deleted_sour_memory_no_longer_affects_next_plan(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "记住我不喜欢太酸", "source": "text"},
    )
    client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "不要记我不喜欢太酸了", "source": "text"},
    )
    client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": "确认", "source": "text"})

    response = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "不喜欢太酸" not in [
        memory["value_json"]["text"]
        for memory in client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]["memories"]
    ]
    assert "降低酸度" not in payload["state"]["active_adjustments"]
    assert "增加鸡蛋比例" not in payload["state"]["active_adjustments"]


def test_mock_demo_main_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    reset = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "reset"})
    plan = client.post("/api/chat", json={"terminal_id": "demo-kitchen-001", "text": PLAN_TEXT, "source": "text"})
    vision = client.post(
        "/api/vision",
        data={"terminal_id": "demo-kitchen-001", "purpose": "ingredients"},
        files={"image": ("ingredients.jpg", b"fake-image", "image/jpeg")},
    )
    start = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "start"})
    sour = client.post(
        "/api/chat",
        json={"terminal_id": "demo-kitchen-001", "text": "记住我不喜欢太酸", "source": "text"},
    )
    next_step = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "next_step"})
    finish = client.post("/api/control", json={"terminal_id": "demo-kitchen-001", "command": "finish"})

    assert all(
        response.status_code == 200
        for response in [reset, plan, vision, start, sour, next_step, finish]
    )
    assert plan.json()["state"]["ui_mode"] == "planning"
    assert vision.json()["state"]["ui_mode"] == "vision"
    assert start.json()["state"]["ui_mode"] == "cooking"
    assert sour.json()["state"]["ui_mode"] == "cooking"
    assert next_step.json()["state"]["current_step_index"] == 1
    assert finish.json()["state"]["ui_mode"] == "review"

    events = client.get("/api/state?terminal_id=demo-kitchen-001").json()["data"]["tool_events"]
    names = [event["name"] for event in events]
    assert "memory_write" in names
    assert "inventory_update" in names
    assert "vision_observe" in names
    assert "recipe_adjust" in names
    assert "finish" in names
    assert all("output_json" not in event for event in events)
