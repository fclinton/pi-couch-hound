"""Tests for configuration CRUD API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import AppConfig


@pytest.fixture
def config_client(tmp_path: Path) -> TestClient:
    """Return a test client with a writable config file."""
    app = create_app()
    with TestClient(app) as client:
        # Point config_path to a temp file so writes don't touch the real config
        app.state.config_path = tmp_path / "config.yaml"
        yield client


def test_get_config(config_client: TestClient):
    """GET /api/config should return the full config."""
    response = config_client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "camera" in data
    assert "detection" in data
    assert "cooldown" in data
    assert "actions" in data
    assert "web" in data
    assert "logging" in data


def test_put_config_replaces_entirely(config_client: TestClient):
    """PUT /api/config should replace the full config and persist."""
    new_config = AppConfig()
    new_config.web.port = 9999
    new_config.cooldown.seconds = 10

    response = config_client.put("/api/config", json=new_config.model_dump(mode="json"))
    assert response.status_code == 200
    data = response.json()
    assert data["web"]["port"] == 9999
    assert data["cooldown"]["seconds"] == 10

    # Verify hot-reload: GET should reflect the change
    response = config_client.get("/api/config")
    assert response.json()["web"]["port"] == 9999


def test_put_config_validation_error(config_client: TestClient):
    """PUT /api/config with invalid data should return 422."""
    bad = AppConfig().model_dump(mode="json")
    bad["detection"]["confidence_threshold"] = 5.0  # Out of [0.0, 1.0]
    response = config_client.put("/api/config", json=bad)
    assert response.status_code == 422


def test_patch_camera_section(config_client: TestClient):
    """PATCH /api/config/camera should merge into the camera section."""
    response = config_client.patch("/api/config/camera", json={"capture_interval": 2.0})
    assert response.status_code == 200
    data = response.json()
    assert data["camera"]["capture_interval"] == 2.0
    # Other camera fields should remain default
    assert data["camera"]["resolution"] == [1280, 720]


def test_patch_cooldown_section(config_client: TestClient):
    """PATCH /api/config/cooldown should update cooldown settings."""
    response = config_client.patch("/api/config/cooldown", json={"seconds": 60})
    assert response.status_code == 200
    assert response.json()["cooldown"]["seconds"] == 60


def test_patch_actions_section(config_client: TestClient):
    """PATCH /api/config/actions should replace the actions list."""
    actions = {
        "actions": [
            {"name": "bark_alarm", "type": "sound", "enabled": True, "sound_file": "woof.wav"}
        ]
    }
    response = config_client.patch("/api/config/actions", json=actions)
    assert response.status_code == 200
    data = response.json()
    assert len(data["actions"]) == 1
    assert data["actions"][0]["name"] == "bark_alarm"


def test_patch_unknown_section(config_client: TestClient):
    """PATCH /api/config/nonexistent should return 404."""
    response = config_client.patch("/api/config/nonexistent", json={"foo": "bar"})
    assert response.status_code == 404


def test_patch_validation_error(config_client: TestClient):
    """PATCH with invalid values should return 422."""
    response = config_client.patch(
        "/api/config/camera", json={"capture_interval": 999.0}
    )
    assert response.status_code == 422


def test_put_then_get_roundtrip(config_client: TestClient):
    """Full config roundtrip: PUT then GET should match."""
    cfg = AppConfig()
    cfg.detection.confidence_threshold = 0.75
    cfg.web.port = 3000

    config_client.put("/api/config", json=cfg.model_dump(mode="json"))
    response = config_client.get("/api/config")
    data = response.json()
    assert data["detection"]["confidence_threshold"] == 0.75
    assert data["web"]["port"] == 3000
