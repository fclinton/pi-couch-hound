"""E2E tests for the Settings page — verify frontend payloads reach the backend."""

from __future__ import annotations

import pytest

pw = pytest.importorskip("playwright.sync_api")


def test_dashboard_loads(page: pw.Page) -> None:  # type: ignore[name-defined]
    """The app should load and render without JS errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.wait_for_load_state("networkidle")
    assert len(errors) == 0, f"JS errors on page load: {errors}"


def test_health_endpoint(live_server: str, page: pw.Page) -> None:  # type: ignore[name-defined]
    """GET /api/health should return ok from the live server."""
    resp = page.request.get(f"{live_server}/api/health")
    assert resp.status == 200
    assert resp.json()["status"] == "ok"


def test_settings_page_navigable(page: pw.Page) -> None:  # type: ignore[name-defined]
    """Navigate to the Settings page and verify it renders."""
    # Click settings link/tab in the nav
    settings_link = page.get_by_role("link", name="Settings")
    if settings_link.count() > 0:
        settings_link.first.click()
        page.wait_for_load_state("networkidle")

    # If no nav link, try direct navigation
    if "settings" not in page.url.lower():
        page.goto(page.url.rstrip("/") + "/settings")
        page.wait_for_load_state("networkidle")

    # Verify at least one settings tab is present
    page.wait_for_selector("text=/Camera|Detection|Actions|Cooldown/i", timeout=5000)


def test_config_api_roundtrip(live_server: str, page: pw.Page) -> None:  # type: ignore[name-defined]
    """Verify config can be read and patched via the API from the browser context."""
    # GET config
    resp = page.request.get(f"{live_server}/api/config")
    assert resp.status == 200
    config = resp.json()
    assert "camera" in config
    assert "actions" in config

    # PATCH camera (same payload shape as CameraTab)
    resp = page.request.patch(
        f"{live_server}/api/config/camera",
        data={"source": 0, "resolution": [1920, 1080], "capture_interval": 1.0},
    )
    assert resp.status == 200
    assert resp.json()["camera"]["resolution"] == [1920, 1080]

    # PATCH actions (same payload shape as ActionsTab — the PR #80 fix)
    resp = page.request.patch(
        f"{live_server}/api/config/actions",
        data={
            "actions": [
                {"name": "test_beep", "type": "sound", "enabled": True, "sound_file": "beep.wav"}
            ]
        },
    )
    assert resp.status == 200
    assert len(resp.json()["actions"]) == 1

    # Verify persistence via GET
    resp = page.request.get(f"{live_server}/api/config")
    assert resp.json()["actions"][0]["name"] == "test_beep"
    assert resp.json()["camera"]["capture_interval"] == 1.0
