"""Tests for the update manager."""

from __future__ import annotations

import json
import tarfile
import urllib.error
from datetime import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from couch_hound import __version__
from couch_hound.config import UpdateConfig
from couch_hound.updater import UpdateManager, UpdateState


def _make_release_json(
    tag: str = "v0.2.0",
    body: str = "Bug fixes and improvements",
    tarball_name: str = "pi-couch-hound-0.2.0.tar.gz",
    tarball_url: str = "https://github.com/fclinton/pi-couch-hound/releases/download/v0.2.0/pi-couch-hound-0.2.0.tar.gz",
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "body": body,
        "assets": [
            {
                "name": tarball_name,
                "browser_download_url": tarball_url,
            }
        ],
    }


@pytest.fixture
def update_config() -> UpdateConfig:
    return UpdateConfig(enabled=True, check_interval_minutes=5)


@pytest.fixture
def manager(update_config: UpdateConfig, tmp_path: Path) -> UpdateManager:
    return UpdateManager(update_config, install_dir=tmp_path)


async def test_check_no_updates(manager: UpdateManager) -> None:
    """When remote version matches current, state is UP_TO_DATE."""
    release = _make_release_json(tag=f"v{__version__}")
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = release
        info = await manager.check_for_updates()

    assert info.state == UpdateState.UP_TO_DATE
    assert info.available_version is None
    assert info.release_url is None


async def test_check_update_available(manager: UpdateManager) -> None:
    """When remote version is newer, state is AVAILABLE with release info."""
    release = _make_release_json(tag="v99.0.0", body="New features")
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = release
        info = await manager.check_for_updates()

    assert info.state == UpdateState.AVAILABLE
    assert info.available_version == "99.0.0"
    assert info.release_notes == "New features"
    assert info.release_url is not None
    assert info.release_url.endswith(".tar.gz")


async def test_check_api_failure_404(manager: UpdateManager) -> None:
    """404 from GitHub API sets ERROR state with 'No releases found'."""
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = urllib.error.HTTPError(
            url="",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,  # type: ignore[arg-type]
        )
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "No releases found" in (info.last_error or "")


async def test_check_api_rate_limit(manager: UpdateManager) -> None:
    """403 from GitHub API sets ERROR state with rate limit message."""
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = urllib.error.HTTPError(
            url="",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,  # type: ignore[arg-type]
        )
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "rate limit" in (info.last_error or "")


async def test_check_network_error(manager: UpdateManager) -> None:
    """Network error sets ERROR state."""
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = urllib.error.URLError("Connection refused")
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "Network error" in (info.last_error or "")


async def test_check_invalid_json(manager: UpdateManager) -> None:
    """Invalid JSON response sets ERROR state."""
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "parse" in (info.last_error or "").lower()


async def test_check_version_comparison(manager: UpdateManager) -> None:
    """Version 0.0.9 should not be treated as an update for 0.1.0."""
    release = _make_release_json(tag="v0.0.9")
    with patch.object(manager, "_fetch_latest_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = release
        info = await manager.check_for_updates()

    assert info.state == UpdateState.UP_TO_DATE


async def test_apply_downloads_and_installs(manager: UpdateManager, tmp_path: Path) -> None:
    """Apply should download tarball, extract, and pip install."""
    manager._info.state = UpdateState.AVAILABLE
    manager._info.release_url = "https://example.com/release.tar.gz"

    # Create a fake tarball
    release_dir = tmp_path / "tarball_src" / "pi-couch-hound-0.2.0"
    release_dir.mkdir(parents=True)
    (release_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    ch_dir = release_dir / "couch_hound"
    ch_dir.mkdir()
    (ch_dir / "__init__.py").write_text('__version__ = "0.2.0"\n')
    tarball_path = str(tmp_path / "release.tar.gz")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(str(release_dir), arcname="pi-couch-hound-0.2.0")

    with (
        patch.object(
            manager, "_download_release", new_callable=AsyncMock, return_value=tarball_path
        ),
        patch("subprocess.run") as mock_subprocess,
        patch("couch_hound.updater.asyncio.get_running_loop") as mock_loop,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_loop.return_value = MagicMock()
        await manager.apply_update()

    # pip install should have been called
    mock_subprocess.assert_called_once()
    # couch_hound dir should have been overlaid
    assert (tmp_path / "couch_hound" / "__init__.py").exists()


async def test_apply_preserves_user_data(manager: UpdateManager, tmp_path: Path) -> None:
    """Apply should preserve config.yaml, data/, logs/, etc."""
    manager._info.state = UpdateState.AVAILABLE
    manager._info.release_url = "https://example.com/release.tar.gz"

    # Create user data that should be preserved
    (tmp_path / "config.yaml").write_text("my: config\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "events.db").write_text("data")

    # Create a fake tarball with a config.yaml that should NOT overwrite
    release_dir = tmp_path / "tarball_src" / "pi-couch-hound-0.2.0"
    release_dir.mkdir(parents=True)
    (release_dir / "config.yaml").write_text("default: config\n")
    (release_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    tarball_path = str(tmp_path / "release.tar.gz")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(str(release_dir), arcname="pi-couch-hound-0.2.0")

    with (
        patch.object(
            manager, "_download_release", new_callable=AsyncMock, return_value=tarball_path
        ),
        patch("subprocess.run") as mock_subprocess,
        patch("couch_hound.updater.asyncio.get_running_loop") as mock_loop,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_loop.return_value = MagicMock()
        await manager.apply_update()

    # User data should be preserved
    assert (tmp_path / "config.yaml").read_text() == "my: config\n"
    assert (tmp_path / "data" / "events.db").read_text() == "data"


async def test_apply_refuses_incompatible_python(manager: UpdateManager) -> None:
    """apply_update should refuse if Python version is incompatible."""
    manager._info.state = UpdateState.AVAILABLE
    manager._info.python_compatible = False
    manager._info.requires_python = ">=3.99"

    info = await manager.apply_update()

    assert info.state == UpdateState.ERROR
    assert ">=3.99" in (info.last_error or "")


async def test_apply_refuses_no_tarball_url(manager: UpdateManager) -> None:
    """apply_update should refuse if no release URL is available."""
    manager._info.state = UpdateState.AVAILABLE
    manager._info.release_url = None

    info = await manager.apply_update()

    assert info.state == UpdateState.ERROR
    assert "tarball URL" in (info.last_error or "")


def test_in_maintenance_window_normal(manager: UpdateManager) -> None:
    """Normal window (e.g., 03:00-05:00) works correctly."""
    manager._config.maintenance_window_start = "03:00"
    manager._config.maintenance_window_end = "05:00"

    with patch("couch_hound.updater.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = time(4, 0)
        assert manager._in_maintenance_window() is True

        mock_dt.now.return_value.time.return_value = time(6, 0)
        assert manager._in_maintenance_window() is False


def test_in_maintenance_window_midnight_crossing(manager: UpdateManager) -> None:
    """Window crossing midnight (e.g., 23:00-05:00) works correctly."""
    manager._config.maintenance_window_start = "23:00"
    manager._config.maintenance_window_end = "05:00"

    with patch("couch_hound.updater.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = time(23, 30)
        assert manager._in_maintenance_window() is True

        mock_dt.now.return_value.time.return_value = time(2, 0)
        assert manager._in_maintenance_window() is True

        mock_dt.now.return_value.time.return_value = time(12, 0)
        assert manager._in_maintenance_window() is False


def test_in_maintenance_window_none(manager: UpdateManager) -> None:
    """When no window is set, always returns True."""
    manager._config.maintenance_window_start = None
    manager._config.maintenance_window_end = None
    assert manager._in_maintenance_window() is True


def test_get_info_returns_current_state(manager: UpdateManager) -> None:
    """get_info returns the current state snapshot."""
    info = manager.get_info()
    assert info.state == UpdateState.UP_TO_DATE
    assert info.current_version == __version__
