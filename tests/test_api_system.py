"""Tests for system API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
