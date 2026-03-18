"""Tests for Chromecast discovery API endpoint."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import AppConfig


@pytest.fixture
def chromecast_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client for chromecast endpoints."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig()
        yield client


def _make_cast(friendly_name: str, model_name: str, uuid_str: str) -> MagicMock:
    """Create a mock Chromecast object."""
    cast = MagicMock()
    cast.cast_info.friendly_name = friendly_name
    cast.cast_info.model_name = model_name
    cast.cast_info.uuid = uuid_str
    return cast


# ── GET /api/chromecasts/discover ──


@patch("couch_hound.api.routes_chromecast.pychromecast", create=True)
def test_discover_chromecasts_success(mock_pycc: MagicMock, chromecast_client: TestClient) -> None:
    """Discovered devices are returned sorted by friendly name."""
    browser = MagicMock()
    mock_pycc.get_chromecasts.return_value = (
        [
            _make_cast("Living Room", "Chromecast Audio", "uuid-2"),
            _make_cast("Bedroom", "Chromecast", "uuid-1"),
        ],
        browser,
    )

    # Patch at the module level where _discover_devices imports pychromecast
    with patch("couch_hound.api.routes_chromecast._discover_devices") as mock_discover:
        from couch_hound.api.schemas import ChromecastDeviceInfo

        mock_discover.return_value = (
            [
                ChromecastDeviceInfo(
                    friendly_name="Bedroom", model_name="Chromecast", uuid="uuid-1"
                ),
                ChromecastDeviceInfo(
                    friendly_name="Living Room",
                    model_name="Chromecast Audio",
                    uuid="uuid-2",
                ),
            ],
            3.21,
        )

        response = chromecast_client.get("/api/chromecasts/discover")

    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 2
    assert data["devices"][0]["friendly_name"] == "Bedroom"
    assert data["devices"][1]["friendly_name"] == "Living Room"
    assert data["devices"][1]["model_name"] == "Chromecast Audio"
    assert isinstance(data["scan_duration"], float)


def test_discover_chromecasts_empty(chromecast_client: TestClient) -> None:
    """Empty network returns empty device list."""
    with patch("couch_hound.api.routes_chromecast._discover_devices") as mock_discover:
        mock_discover.return_value = ([], 5.0)
        response = chromecast_client.get("/api/chromecasts/discover")

    assert response.status_code == 200
    data = response.json()
    assert data["devices"] == []
    assert data["scan_duration"] == 5.0


def test_discover_chromecasts_custom_timeout(chromecast_client: TestClient) -> None:
    """Custom timeout parameter is passed through."""
    with patch("couch_hound.api.routes_chromecast._discover_devices") as mock_discover:
        mock_discover.return_value = ([], 3.0)
        response = chromecast_client.get("/api/chromecasts/discover?timeout=3")

    assert response.status_code == 200
    mock_discover.assert_called_once_with(3.0)


def test_discover_chromecasts_timeout_clamped_high(chromecast_client: TestClient) -> None:
    """Timeout above 15 is rejected by validation."""
    response = chromecast_client.get("/api/chromecasts/discover?timeout=60")
    assert response.status_code == 422


def test_discover_chromecasts_timeout_clamped_low(chromecast_client: TestClient) -> None:
    """Timeout below 1 is rejected by validation."""
    response = chromecast_client.get("/api/chromecasts/discover?timeout=0.1")
    assert response.status_code == 422


def test_discover_chromecasts_error(tmp_path: Path) -> None:
    """Discovery error returns 500."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig()
        with patch("couch_hound.api.routes_chromecast._discover_devices") as mock_discover:
            mock_discover.side_effect = RuntimeError("zeroconf failed")
            response = client.get("/api/chromecasts/discover")

    assert response.status_code == 500
