"""Tests for system API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import ActionConfig, AppConfig


def test_health_check(client: TestClient):
    """Health endpoint should return ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status(client: TestClient):
    """Status endpoint should return running status."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "uptime_seconds" in data
    assert data["version"] == "0.1.0"


# ── POST /api/test-actions ──


@pytest.fixture
def system_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with seeded actions for system endpoint tests."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            actions=[
                ActionConfig(name="echo_test", type="script", enabled=True, command="echo hi"),
                ActionConfig(name="disabled_one", type="script", enabled=False, command="echo no"),
            ]
        )
        yield client


@pytest.fixture
def no_actions_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with no actions configured."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(actions=[])
        yield client


def test_test_actions_fires_enabled_only(system_client: TestClient) -> None:
    """POST /api/test-actions should only fire enabled actions."""
    response = system_client.post("/api/test-actions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "echo_test"
    assert data["results"][0]["success"] is True


def test_test_actions_empty(no_actions_client: TestClient) -> None:
    """POST /api/test-actions with no actions returns empty results."""
    response = no_actions_client.post("/api/test-actions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["succeeded"] == 0
    assert data["failed"] == 0
    assert data["results"] == []


def test_test_actions_with_failure(tmp_path: Path) -> None:
    """POST /api/test-actions reports failures per action."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            actions=[
                ActionConfig(
                    name="bad_sound",
                    type="sound",
                    enabled=True,
                    sound_file="nonexistent.wav",
                ),
            ]
        )
        response = client.post("/api/test-actions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["failed"] == 1
        assert data["results"][0]["success"] is False
        assert data["results"][0]["message"]  # has an error message


# ── POST /api/restart ──


def test_restart_pipeline(client: TestClient) -> None:
    """POST /api/restart should restart the pipeline and return success."""
    mock_pipeline = AsyncMock()
    client.app.state.pipeline = mock_pipeline  # type: ignore[union-attr]

    response = client.post("/api/restart")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Pipeline restarted successfully"
    mock_pipeline.restart.assert_awaited_once()
