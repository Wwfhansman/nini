from fastapi.testclient import TestClient

from backend.agent.schemas import sanitize_ui_patch
from backend.app import app


TERMINAL_ID = "demo-kitchen-001"
PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nini-ui-patch-test.db"))
    monkeypatch.setenv("DEFAULT_TERMINAL_ID", TERMINAL_ID)
    monkeypatch.setenv("DEMO_MODE", "mock")
    return TestClient(app)


def _reset(client: TestClient):
    return client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": "reset"})


def _plan(client: TestClient):
    return client.post("/api/chat", json={"terminal_id": TERMINAL_ID, "text": PLAN_TEXT, "source": "text"})


def test_ui_patch_sanitize_bounds_and_tones():
    patch = sanitize_ui_patch(
        {
            "title": "菜" * 80,
            "subtitle": "说明" * 80,
            "attention": "重点" * 80,
            "cards": [
                {"label": f"标签{i}" * 10, "value": f"内容{i}" * 50, "tone": "bad-tone"}
                for i in range(8)
            ],
            "suggested_phrases": [f"建议{i}" * 20 for i in range(7)],
        }
    )

    assert len(patch["title"]) == 60
    assert len(patch["subtitle"]) == 120
    assert len(patch["attention"]) == 120
    assert len(patch["cards"]) == 6
    assert len(patch["cards"][0]["label"]) == 20
    assert len(patch["cards"][0]["value"]) == 80
    assert patch["cards"][0]["tone"] == "neutral"
    assert len(patch["suggested_phrases"]) == 5
    assert len(patch["suggested_phrases"][0]) == 30


def test_planning_state_persists_ui_patch(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)

    response = _plan(client)

    assert response.status_code == 200
    patch = response.json()["state"]["ui_patch"]
    assert "低脂不辣番茄鸡胸肉滑蛋" in patch["title"]
    labels = {card["label"] for card in patch["cards"]}
    assert {"健康目标", "饮食限制"}.issubset(labels)
    assert patch["suggested_phrases"]


def test_vision_state_ui_patch_attention_mentions_adjustment(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    _plan(client)

    response = client.post(
        "/api/vision",
        data={"terminal_id": TERMINAL_ID, "purpose": "ingredients"},
        files={"image": ("ingredients.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    patch = response.json()["state"]["ui_patch"]
    assert patch["title"] == "我看到了这些食材"
    assert "番茄只有半个" in patch["attention"]
    assert any(card["label"] == "番茄" for card in patch["cards"])


def test_finish_state_ui_patch_shows_review(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    _plan(client)
    client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": "start"})

    response = client.post("/api/control", json={"terminal_id": TERMINAL_ID, "command": "finish"})

    assert response.status_code == 200
    patch = response.json()["state"]["ui_patch"]
    assert patch["title"] == "本次烹饪复盘"
    assert any(card["label"] in {"食材消耗", "下次建议"} for card in patch["cards"])


def test_reset_clears_previous_ui_patch(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _reset(client)
    _plan(client)

    response = _reset(client)

    assert response.status_code == 200
    assert response.json()["state"]["ui_patch"] == {}
