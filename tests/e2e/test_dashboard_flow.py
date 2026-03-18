"""E2E tests for the Dashboard page."""

from __future__ import annotations

import pytest

pw = pytest.importorskip("playwright.sync_api")


def test_status_api_from_browser(live_server: str, page: pw.Page) -> None:  # type: ignore[name-defined]
    """GET /api/status returns valid status from the live server."""
    resp = page.request.get(f"{live_server}/api/status")
    assert resp.status == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "version" in data
    assert "monitoring_enabled" in data


def test_monitoring_toggle_via_api(live_server: str, page: pw.Page) -> None:  # type: ignore[name-defined]
    """PUT /api/monitoring toggles monitoring state (same payload as frontend)."""
    # Disable
    resp = page.request.put(
        f"{live_server}/api/monitoring",
        data={"enabled": False},
    )
    assert resp.status == 200
    assert resp.json()["enabled"] is False

    # Enable
    resp = page.request.put(
        f"{live_server}/api/monitoring",
        data={"enabled": True},
    )
    assert resp.status == 200
    assert resp.json()["enabled"] is True
