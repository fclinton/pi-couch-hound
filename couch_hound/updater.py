"""Automatic update manager — checks GitHub for updates and applies them."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import StrEnum
from pathlib import Path

from couch_hound.config import UpdateConfig

logger = logging.getLogger(__name__)


class UpdateState(StrEnum):
    UP_TO_DATE = "up_to_date"
    CHECKING = "checking"
    AVAILABLE = "available"
    APPLYING = "applying"
    ERROR = "error"


@dataclass
class UpdateInfo:
    state: UpdateState = UpdateState.UP_TO_DATE
    current_commit: str = ""
    remote_commit: str | None = None
    current_version: str = ""
    available_version: str | None = None
    last_check_time: str | None = None
    last_error: str | None = None
    commits_behind: int = 0
    commit_messages: list[str] = field(default_factory=list)


class UpdateManager:
    """Manages checking for and applying updates from the Git remote."""

    def __init__(self, config: UpdateConfig, repo_dir: Path | None = None) -> None:
        self._config = config
        self._repo_dir = repo_dir or Path.cwd()
        self._info = UpdateInfo()
        self._default_branch: str | None = None
        self._task: asyncio.Task[None] | None = None

        from couch_hound import __version__

        self._info.current_version = __version__

    def get_info(self) -> UpdateInfo:
        """Return a snapshot of the current update state."""
        return self._info

    def update_config(self, config: UpdateConfig) -> None:
        """Hot-reload update configuration."""
        self._config = config

    async def start(self, stop_event: asyncio.Event) -> asyncio.Task[None] | None:
        """Start the periodic update check loop if enabled."""
        if not self._config.enabled:
            return None
        self._task = asyncio.create_task(self._periodic_check_loop(stop_event))
        logger.info("Update checker started (interval=%dm)", self._config.check_interval_minutes)
        return self._task

    async def check_for_updates(self) -> UpdateInfo:
        """Check the remote for new commits."""
        self._info.state = UpdateState.CHECKING
        self._info.last_error = None
        try:
            await self._run_git("fetch", "origin")

            branch = await self._get_default_branch()
            local = (await self._run_git("rev-parse", "HEAD")).strip()
            remote = (await self._run_git("rev-parse", f"origin/{branch}")).strip()

            self._info.current_commit = local[:8]

            if local == remote:
                self._info.state = UpdateState.UP_TO_DATE
                self._info.remote_commit = None
                self._info.available_version = None
                self._info.commits_behind = 0
                self._info.commit_messages = []
            else:
                self._info.state = UpdateState.AVAILABLE
                self._info.remote_commit = remote[:8]
                count_str = (
                    await self._run_git("rev-list", "--count", f"HEAD..origin/{branch}")
                ).strip()
                self._info.commits_behind = int(count_str)

                log_output = await self._run_git("log", "--oneline", f"HEAD..origin/{branch}")
                self._info.commit_messages = [
                    line.strip() for line in log_output.strip().splitlines() if line.strip()
                ]

                # Try to extract remote version
                try:
                    init_content = await self._run_git(
                        "show", f"origin/{branch}:couch_hound/__init__.py"
                    )
                    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
                    self._info.available_version = match.group(1) if match else None
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    self._info.available_version = None

            self._info.last_check_time = datetime.now().isoformat()

        except FileNotFoundError:
            self._info.state = UpdateState.ERROR
            self._info.last_error = "git is not installed"
            logger.error("git executable not found")
        except subprocess.CalledProcessError as exc:
            self._info.state = UpdateState.ERROR
            self._info.last_error = f"git command failed: {exc.stderr or exc.stdout or str(exc)}"
            logger.error("Update check failed: %s", self._info.last_error)
        except subprocess.TimeoutExpired:
            self._info.state = UpdateState.ERROR
            self._info.last_error = "git command timed out"
            logger.error("Update check timed out")

        return self._info

    async def apply_update(self) -> UpdateInfo:
        """Pull latest code, reinstall, rebuild frontend if needed, then restart."""
        self._info.state = UpdateState.APPLYING
        self._info.last_error = None
        stashed = False

        try:
            branch = await self._get_default_branch()

            # Stash local changes
            stash_out = await self._run_git("stash", "--include-untracked")
            stashed = "No local changes" not in stash_out

            # Pull with fast-forward only
            await self._run_git("pull", "origin", branch, "--ff-only")

            # Reinstall Python package
            venv_python = sys.executable
            await asyncio.to_thread(
                subprocess.run,
                [venv_python, "-m", "pip", "install", "--quiet", "."],
                cwd=str(self._repo_dir),
                capture_output=True,
                text=True,
                timeout=300,
                check=True,
            )
            logger.info("Python package reinstalled")

            # Check if frontend changed
            try:
                diff_output = await self._run_git(
                    "diff",
                    "--name-only",
                    f"HEAD~{self._info.commits_behind}..HEAD",
                    "--",
                    "frontend/",
                )
                if diff_output.strip():
                    logger.info("Frontend files changed, rebuilding...")
                    frontend_dir = self._repo_dir / "frontend"
                    await asyncio.to_thread(
                        subprocess.run,
                        ["npm", "ci", "--silent"],
                        cwd=str(frontend_dir),
                        capture_output=True,
                        text=True,
                        timeout=600,
                        check=True,
                    )
                    await asyncio.to_thread(
                        subprocess.run,
                        ["npm", "run", "build", "--silent"],
                        cwd=str(frontend_dir),
                        capture_output=True,
                        text=True,
                        timeout=600,
                        check=True,
                    )
                    logger.info("Frontend rebuilt")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.warning("Frontend rebuild failed (continuing): %s", exc)

            # Pop stash if we stashed
            if stashed:
                try:
                    await self._run_git("stash", "pop")
                except subprocess.CalledProcessError:
                    logger.warning(
                        "git stash pop had conflicts — local changes may need manual merge"
                    )

            logger.info("Update applied successfully, scheduling restart...")

            # Schedule process exit after a delay so the HTTP response can flush
            loop = asyncio.get_running_loop()
            loop.call_later(2, os._exit, 75)

            return self._info

        except subprocess.CalledProcessError as exc:
            self._info.state = UpdateState.ERROR
            stderr = exc.stderr or exc.stdout or str(exc)
            self._info.last_error = f"Update failed: {stderr}"
            logger.error("Update apply failed: %s", self._info.last_error)
            if stashed:
                try:
                    await self._run_git("stash", "pop")
                except subprocess.CalledProcessError:
                    logger.warning("Failed to pop stash after error")
            return self._info
        except subprocess.TimeoutExpired:
            self._info.state = UpdateState.ERROR
            self._info.last_error = "Update command timed out"
            logger.error("Update apply timed out")
            if stashed:
                try:
                    await self._run_git("stash", "pop")
                except subprocess.CalledProcessError:
                    logger.warning("Failed to pop stash after timeout")
            return self._info

    async def _periodic_check_loop(self, stop_event: asyncio.Event) -> None:
        """Background loop that periodically checks for updates."""
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._config.check_interval_minutes * 60,
                )
                break  # stop_event was set
            except TimeoutError:
                pass  # interval elapsed, time to check

            await self.check_for_updates()

            if (
                self._info.state == UpdateState.AVAILABLE
                and self._config.auto_apply
                and self._in_maintenance_window()
            ):
                logger.info("Auto-applying update (within maintenance window)")
                await self.apply_update()

    def _in_maintenance_window(self) -> bool:
        """Check if current local time is within the configured maintenance window."""
        start_str = self._config.maintenance_window_start
        end_str = self._config.maintenance_window_end

        # No window configured means always OK
        if start_str is None or end_str is None:
            return True

        now = datetime.now().time()
        start = time(int(start_str[:2]), int(start_str[3:]))
        end = time(int(end_str[:2]), int(end_str[3:]))

        if start <= end:
            # Normal window (e.g., 03:00-05:00)
            return start <= now <= end
        else:
            # Window crosses midnight (e.g., 23:00-05:00)
            return now >= start or now <= end

    async def _get_default_branch(self) -> str:
        """Detect the default branch name from the remote."""
        if self._default_branch:
            return self._default_branch

        try:
            ref = await self._run_git("symbolic-ref", "refs/remotes/origin/HEAD")
            # Output like "refs/remotes/origin/main"
            self._default_branch = ref.strip().split("/")[-1]
        except subprocess.CalledProcessError:
            self._default_branch = "main"

        return self._default_branch

    async def _run_git(self, *args: str) -> str:
        """Run a git command and return stdout."""
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", *args],
            cwd=str(self._repo_dir),
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return result.stdout
