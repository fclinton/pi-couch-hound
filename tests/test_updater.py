"""Tests for the update manager."""

from __future__ import annotations

import subprocess
from datetime import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from couch_hound.config import UpdateConfig
from couch_hound.updater import UpdateManager, UpdateState


@pytest.fixture
def update_config() -> UpdateConfig:
    return UpdateConfig(enabled=True, check_interval_minutes=5)


@pytest.fixture
def manager(update_config: UpdateConfig, tmp_path: Path) -> UpdateManager:
    return UpdateManager(update_config, repo_dir=tmp_path)


async def test_check_no_updates(manager: UpdateManager) -> None:
    """When local and remote are the same commit, state is UP_TO_DATE."""
    commit = "abc1234567890"
    with patch.object(manager, "_run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            "",  # fetch
            "main",  # symbolic-ref
            commit + "\n",  # rev-parse HEAD
            commit + "\n",  # rev-parse origin/main
        ]
        info = await manager.check_for_updates()

    assert info.state == UpdateState.UP_TO_DATE
    assert info.commits_behind == 0
    assert info.commit_messages == []


async def test_check_update_available(manager: UpdateManager) -> None:
    """When remote is ahead, state is AVAILABLE with commit info."""
    with patch.object(manager, "_run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            "",  # fetch
            "main",  # symbolic-ref
            "aaa1111\n",  # rev-parse HEAD
            "bbb2222\n",  # rev-parse origin/main
            "3\n",  # rev-list --count
            "bbb2222 fix bug\nccc3333 add feature\nddd4444 update docs\n",  # log
            '__version__ = "0.2.0"\n',  # show __init__.py
        ]
        info = await manager.check_for_updates()

    assert info.state == UpdateState.AVAILABLE
    assert info.commits_behind == 3
    assert len(info.commit_messages) == 3
    assert info.available_version == "0.2.0"
    assert info.remote_commit == "bbb2222\n".strip()[:8]


async def test_check_git_fetch_failure(manager: UpdateManager) -> None:
    """Git fetch failure sets ERROR state."""
    with patch.object(manager, "_run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="fatal: unable to access"
        )
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert info.last_error is not None
    assert "fatal: unable to access" in info.last_error


async def test_check_git_not_installed(manager: UpdateManager) -> None:
    """Missing git sets ERROR state."""
    with patch.object(manager, "_run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = FileNotFoundError("git not found")
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "not installed" in (info.last_error or "")


async def test_check_timeout(manager: UpdateManager) -> None:
    """Git timeout sets ERROR state."""
    with patch.object(manager, "_run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = subprocess.TimeoutExpired("git", 60)
        info = await manager.check_for_updates()

    assert info.state == UpdateState.ERROR
    assert "timed out" in (info.last_error or "")


async def test_apply_runs_correct_commands(manager: UpdateManager) -> None:
    """Apply should run git pull, pip install, in correct order."""
    manager._info.commits_behind = 2
    manager._info.state = UpdateState.AVAILABLE

    commands_run: list[tuple[str, ...]] = []

    async def mock_run_git(*args: str) -> str:
        commands_run.append(args)
        if args[0] == "symbolic-ref":
            return "refs/remotes/origin/main"
        if args[0] == "stash" and args[1] == "--include-untracked":
            return "No local changes to save"
        if args[0] == "diff":
            return ""  # no frontend changes
        return ""

    with (
        patch.object(manager, "_run_git", side_effect=mock_run_git),
        patch("subprocess.run") as mock_subprocess,
        patch("couch_hound.updater.asyncio.get_running_loop") as mock_loop,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_loop.return_value = MagicMock()
        await manager.apply_update()

    git_commands = [c[0] for c in commands_run]
    assert "stash" in git_commands
    assert "pull" in git_commands
    # pip install is called via subprocess.run
    mock_subprocess.assert_called_once()


async def test_apply_with_frontend_changes(manager: UpdateManager) -> None:
    """Apply should rebuild frontend when frontend files changed."""
    manager._info.commits_behind = 1
    manager._info.state = UpdateState.AVAILABLE

    async def mock_run_git(*args: str) -> str:
        if args[0] == "symbolic-ref":
            return "refs/remotes/origin/main"
        if args[0] == "stash" and args[1] == "--include-untracked":
            return "No local changes to save"
        if args[0] == "diff":
            return "frontend/src/App.tsx\nfrontend/package.json\n"
        return ""

    with (
        patch.object(manager, "_run_git", side_effect=mock_run_git),
        patch("subprocess.run") as mock_subprocess,
        patch("couch_hound.updater.asyncio.get_running_loop") as mock_loop,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_loop.return_value = MagicMock()
        await manager.apply_update()

    # pip install + npm ci + npm run build = 3 subprocess.run calls
    assert mock_subprocess.call_count == 3


async def test_apply_ff_only_failure(manager: UpdateManager) -> None:
    """If git pull --ff-only fails, state is ERROR and stash is popped."""
    manager._info.commits_behind = 1
    manager._info.state = UpdateState.AVAILABLE

    call_count = 0

    async def mock_run_git(*args: str) -> str:
        nonlocal call_count
        call_count += 1
        if args[0] == "symbolic-ref":
            return "refs/remotes/origin/main"
        if args[0] == "stash" and args[1] == "--include-untracked":
            return "Saved working directory"
        if args[0] == "pull":
            raise subprocess.CalledProcessError(1, "git", stderr="cannot fast-forward")
        if args[0] == "stash" and args[1] == "pop":
            return ""
        return ""

    with patch.object(manager, "_run_git", side_effect=mock_run_git):
        info = await manager.apply_update()

    assert info.state == UpdateState.ERROR
    assert "cannot fast-forward" in (info.last_error or "")


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
    assert info.current_version == "0.1.0"
