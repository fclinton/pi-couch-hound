"""Tests for update API endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.updater import UpdateInfo, UpdateState


@pytest.fixture
def update_client() -> Iterator[TestClient]:
    """Return a test client with lifespan (so update_manager is available)."""
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_get_update_status(update_client: TestClient) -> None:
    """GET /api/update/status returns the current update state."""
    response = update_client.get("/api/update/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "up_to_date"
    assert "current_version" in data
    assert "commits_behind" in data


def test_check_for_updates(update_client: TestClient) -> None:
    """POST /api/update/check triggers a check and returns status."""
    manager = update_client.app.state.update_manager  # type: ignore[union-attr]
    with patch.object(manager, "check_for_updates", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = UpdateInfo(state=UpdateState.UP_TO_DATE)
        response = update_client.post("/api/update/check")

    assert response.status_code == 200
    mock_check.assert_called_once()


def test_apply_update_when_not_available(update_client: TestClient) -> None:
    """POST /api/update/apply returns 409 when no update is available."""
    response = update_client.post("/api/update/apply")
    assert response.status_code == 409


def test_apply_update_when_available(update_client: TestClient) -> None:
    """POST /api/update/apply succeeds when an update is available."""
    manager = update_client.app.state.update_manager  # type: ignore[union-attr]
    manager._info.state = UpdateState.AVAILABLE

    with patch.object(manager, "apply_update", new_callable=AsyncMock) as mock_apply:
        mock_apply.return_value = UpdateInfo(state=UpdateState.APPLYING)
        response = update_client.post("/api/update/apply")

    assert response.status_code == 200
    mock_apply.assert_called_once()
