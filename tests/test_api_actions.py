"""Tests for actions CRUD API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import ActionConfig, AppConfig


@pytest.fixture
def actions_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client seeded with two actions."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            actions=[
                ActionConfig(name="bark_alarm", type="sound", enabled=True, sound_file="woof.wav"),
                ActionConfig(name="save_snap", type="snapshot", enabled=True, save_dir="snaps/"),
            ]
        )
        yield client


@pytest.fixture
def empty_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with no actions."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(actions=[])
        yield client


# ── GET /api/actions ──


def test_list_actions(actions_client: TestClient) -> None:
    response = actions_client.get("/api/actions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [a["name"] for a in data]
    assert "bark_alarm" in names
    assert "save_snap" in names


def test_list_actions_empty(empty_client: TestClient) -> None:
    response = empty_client.get("/api/actions")
    assert response.status_code == 200
    assert response.json() == []


# ── POST /api/actions ──


def test_create_action(actions_client: TestClient) -> None:
    new_action = {"name": "http_notify", "type": "http", "url": "https://example.com/hook"}
    response = actions_client.post("/api/actions", json=new_action)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "http_notify"
    assert data["type"] == "http"
    assert data["enabled"] is True  # default

    # Verify it shows up in the list
    response = actions_client.get("/api/actions")
    assert len(response.json()) == 3


def test_create_action_duplicate_name(actions_client: TestClient) -> None:
    duplicate = {"name": "bark_alarm", "type": "sound", "sound_file": "bark.wav"}
    response = actions_client.post("/api/actions", json=duplicate)
    assert response.status_code == 409


def test_create_action_invalid_type(actions_client: TestClient) -> None:
    bad = {"name": "bad_action", "type": "invalid_type"}
    response = actions_client.post("/api/actions", json=bad)
    assert response.status_code == 422


# ── PUT /api/actions/{name} ──


def test_update_action(actions_client: TestClient) -> None:
    updated = {"name": "bark_alarm", "type": "sound", "sound_file": "new_bark.wav", "volume": 80}
    response = actions_client.put("/api/actions/bark_alarm", json=updated)
    assert response.status_code == 200
    data = response.json()
    assert data["sound_file"] == "new_bark.wav"
    assert data["volume"] == 80

    # Verify persistence via GET
    response = actions_client.get("/api/actions")
    alarm = next(a for a in response.json() if a["name"] == "bark_alarm")
    assert alarm["sound_file"] == "new_bark.wav"


def test_update_action_not_found(actions_client: TestClient) -> None:
    body = {"name": "nonexistent", "type": "sound"}
    response = actions_client.put("/api/actions/nonexistent", json=body)
    assert response.status_code == 404


def test_update_action_name_conflict(actions_client: TestClient) -> None:
    # Try to rename bark_alarm to save_snap (already taken)
    body = {"name": "save_snap", "type": "sound", "sound_file": "woof.wav"}
    response = actions_client.put("/api/actions/bark_alarm", json=body)
    assert response.status_code == 409


# ── DELETE /api/actions/{name} ──


def test_delete_action(actions_client: TestClient) -> None:
    response = actions_client.delete("/api/actions/bark_alarm")
    assert response.status_code == 204

    # Verify removed
    response = actions_client.get("/api/actions")
    names = [a["name"] for a in response.json()]
    assert "bark_alarm" not in names
    assert len(response.json()) == 1


def test_delete_action_not_found(actions_client: TestClient) -> None:
    response = actions_client.delete("/api/actions/nonexistent")
    assert response.status_code == 404


# ── POST /api/actions/{name}/test ──


def test_fire_action_script_success(empty_client: TestClient) -> None:
    # Create a script action that runs echo
    action = {"name": "echo_test", "type": "script", "command": "echo hello"}
    empty_client.post("/api/actions", json=action)

    response = empty_client.post("/api/actions/echo_test/test")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "echo_test"
    assert data["success"] is True


def test_fire_action_failure_returns_error(actions_client: TestClient) -> None:
    # sound action will fail because the sound file doesn't exist on disk
    response = actions_client.post("/api/actions/bark_alarm/test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"]  # should contain an error message


def test_fire_action_not_found(actions_client: TestClient) -> None:
    response = actions_client.post("/api/actions/nonexistent/test")
    assert response.status_code == 404


# ── PATCH /api/actions/{name}/toggle ──


def test_toggle_action_disable(actions_client: TestClient) -> None:
    response = actions_client.patch("/api/actions/bark_alarm/toggle")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "bark_alarm"
    assert data["enabled"] is False


def test_toggle_action_enable(actions_client: TestClient) -> None:
    # First disable
    actions_client.patch("/api/actions/bark_alarm/toggle")
    # Then re-enable
    response = actions_client.patch("/api/actions/bark_alarm/toggle")
    assert response.status_code == 200
    assert response.json()["enabled"] is True


def test_toggle_action_not_found(actions_client: TestClient) -> None:
    response = actions_client.patch("/api/actions/nonexistent/toggle")
    assert response.status_code == 404


# ── Persistence ──


def test_create_action_persists_to_disk(actions_client: TestClient, tmp_path: Path) -> None:
    action = {"name": "persist_test", "type": "script", "command": "echo persist"}
    actions_client.post("/api/actions", json=action)

    # Read the YAML file and verify
    config_file = tmp_path / "config.yaml"
    assert config_file.exists()
    content = config_file.read_text()
    assert "persist_test" in content
