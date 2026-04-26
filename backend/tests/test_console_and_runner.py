from fastapi.testclient import TestClient

from backend.app import app
from scripts.run_mock_demo import StepResult, demo_failed, p0_model_called_false, validate_demo_summary


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001")
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


def test_static_test_console_is_accessible(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/static/test-console.html")

    assert response.status_code == 200
    assert "tool_events" in response.text


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
