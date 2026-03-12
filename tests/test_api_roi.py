"""Tests for ROI API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app


@pytest.fixture
def roi_client(tmp_path: Path) -> TestClient:
    """Return a test client with a writable config file."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        yield client


def test_get_roi_returns_defaults(roi_client: TestClient):
    """GET /api/roi should return the default ROI settings."""
    response = roi_client.get("/api/roi")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert len(data["polygon"]) == 4
    assert data["min_overlap"] == 0.3


def test_put_roi_saves_polygon(roi_client: TestClient):
    """PUT /api/roi should save a new polygon and enable ROI."""
    polygon = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    response = roi_client.put("/api/roi", json={"polygon": polygon})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["polygon"] == polygon
    assert data["min_overlap"] == 0.3  # Default preserved


def test_put_roi_with_min_overlap(roi_client: TestClient):
    """PUT /api/roi with min_overlap should update both polygon and overlap."""
    polygon = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
    response = roi_client.put("/api/roi", json={"polygon": polygon, "min_overlap": 0.5})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["polygon"] == polygon
    assert data["min_overlap"] == 0.5


def test_put_roi_too_few_points(roi_client: TestClient):
    """PUT /api/roi with fewer than 3 points should return 422."""
    response = roi_client.put("/api/roi", json={"polygon": [[0.1, 0.2], [0.3, 0.4]]})
    assert response.status_code == 422


def test_put_roi_invalid_point_length(roi_client: TestClient):
    """PUT /api/roi with a point that has wrong number of coords should return 422."""
    response = roi_client.put(
        "/api/roi", json={"polygon": [[0.1, 0.2], [0.3, 0.4, 0.5], [0.6, 0.7]]}
    )
    assert response.status_code == 422


def test_put_roi_out_of_range(roi_client: TestClient):
    """PUT /api/roi with coordinates outside [0, 1] should return 422."""
    response = roi_client.put("/api/roi", json={"polygon": [[0.0, 0.0], [1.5, 0.0], [1.0, 1.0]]})
    assert response.status_code == 422


def test_delete_roi_clears_and_disables(roi_client: TestClient):
    """DELETE /api/roi should disable ROI and reset to defaults."""
    # First enable ROI
    polygon = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    roi_client.put("/api/roi", json={"polygon": polygon, "min_overlap": 0.7})

    # Then clear it
    response = roi_client.delete("/api/roi")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["min_overlap"] == 0.3


def test_put_then_get_roundtrip(roi_client: TestClient):
    """PUT then GET should return the saved ROI."""
    polygon = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
    roi_client.put("/api/roi", json={"polygon": polygon, "min_overlap": 0.6})

    response = roi_client.get("/api/roi")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["polygon"] == polygon
    assert data["min_overlap"] == 0.6


def test_put_roi_persists_to_full_config(roi_client: TestClient):
    """PUT /api/roi should also be reflected in the full config."""
    polygon = [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7]]
    roi_client.put("/api/roi", json={"polygon": polygon})

    response = roi_client.get("/api/config")
    assert response.status_code == 200
    roi_data = response.json()["detection"]["roi"]
    assert roi_data["enabled"] is True
    assert roi_data["polygon"] == polygon
