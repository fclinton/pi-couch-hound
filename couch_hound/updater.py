"""Automatic update manager — checks GitHub Releases for updates and applies them."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

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
    current_version: str = ""
    available_version: str | None = None
    release_url: str | None = None
    release_notes: str | None = None
    last_check_time: str | None = None
    last_error: str | None = None
    requires_python: str | None = None
    python_compatible: bool = True


# Directories/files to preserve when overlaying an update
_PRESERVE = {"config.yaml", "data", "logs", "snapshots", "models", ".venv"}


class UpdateManager:
    """Manages checking for and applying updates from GitHub Releases."""

    def __init__(self, config: UpdateConfig, install_dir: Path | None = None) -> None:
        self._config = config
        self._install_dir = install_dir or Path.cwd()
        self._info = UpdateInfo()
        self._task: asyncio.Task[None] | None = None

        from couch_hound import __repo__, __version__

        self._info.current_version = __version__
        self._repo = __repo__
        self._api_base = f"https://api.github.com/repos/{self._repo}/releases"

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
        """Check GitHub Releases for a newer version."""
        self._info.state = UpdateState.CHECKING
        self._info.last_error = None
        try:
            data = await self._fetch_latest_release()

            tag = data.get("tag_name", "")

            is_newer: bool
            display_version: str

            if self._config.channel == "nightly":
                # Nightly tags look like "nightly-20260318"; compare against the
                # tag that produced the currently running build (stored in
                # current_version for nightly installs) or always offer if the
                # user just switched to the nightly channel from a semver build.
                display_version = tag
                is_newer = tag != self._info.current_version
            else:
                remote_version_str = tag.lstrip("v")
                display_version = remote_version_str
                try:
                    remote_version = Version(remote_version_str)
                    current_version = Version(self._info.current_version)
                except InvalidVersion as exc:
                    self._info.state = UpdateState.ERROR
                    self._info.last_error = f"Invalid version format: {exc}"
                    self._info.last_check_time = datetime.now().isoformat()
                    return self._info
                is_newer = remote_version > current_version

            if not is_newer:
                self._info.state = UpdateState.UP_TO_DATE
                self._info.available_version = None
                self._info.release_url = None
                self._info.release_notes = None
                self._info.requires_python = None
                self._info.python_compatible = True
            else:
                self._info.state = UpdateState.AVAILABLE
                self._info.available_version = display_version
                self._info.release_notes = data.get("body")

                # Find the tarball asset
                assets = data.get("assets", [])
                tarball_url = None
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".tar.gz"):
                        tarball_url = asset.get("browser_download_url")
                        break
                self._info.release_url = tarball_url

                # Check Python compatibility from release body
                self._info.requires_python = None
                self._info.python_compatible = True

            self._info.last_check_time = datetime.now().isoformat()

        except urllib.error.HTTPError as exc:
            self._info.state = UpdateState.ERROR
            if exc.code == 404:
                self._info.last_error = "No releases found"
            elif exc.code in (403, 429):
                self._info.last_error = "GitHub API rate limit exceeded"
            else:
                self._info.last_error = f"GitHub API error: HTTP {exc.code}"
            logger.error("Update check failed: %s", self._info.last_error)
        except urllib.error.URLError as exc:
            self._info.state = UpdateState.ERROR
            self._info.last_error = f"Network error: {exc.reason}"
            logger.error("Update check failed: %s", self._info.last_error)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self._info.state = UpdateState.ERROR
            self._info.last_error = f"Failed to parse release data: {exc}"
            logger.error("Update check failed: %s", self._info.last_error)

        return self._info

    async def apply_update(self) -> UpdateInfo:
        """Download and apply the latest release, then restart."""
        if not self._info.python_compatible:
            self._info.state = UpdateState.ERROR
            self._info.last_error = (
                f"Update requires Python {self._info.requires_python}, "
                f"but the current interpreter is Python "
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}. "
                f"Please upgrade Python before applying this update."
            )
            return self._info

        if not self._info.release_url:
            self._info.state = UpdateState.ERROR
            self._info.last_error = "No release tarball URL available"
            return self._info

        self._info.state = UpdateState.APPLYING
        self._info.last_error = None

        try:
            # Download tarball to temp file
            tarball_path = await self._download_release(self._info.release_url)

            try:
                # Extract and overlay
                await self._extract_and_overlay(tarball_path)
            finally:
                # Clean up downloaded tarball
                try:
                    os.unlink(tarball_path)
                except OSError:
                    pass

            # Reinstall Python package
            uv_path = shutil.which("uv")
            if uv_path:
                await asyncio.to_thread(
                    subprocess.run,
                    [uv_path, "sync", "--extra", "dev"],
                    cwd=str(self._install_dir),
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=True,
                )
            else:
                venv_python = sys.executable
                await asyncio.to_thread(
                    subprocess.run,
                    [venv_python, "-m", "pip", "install", "--quiet", "."],
                    cwd=str(self._install_dir),
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=True,
                )
            logger.info("Python package reinstalled")

            # Migrate config to pick up new fields / drop removed ones
            try:
                from couch_hound.config import migrate_config

                migrate_config(self._install_dir)
            except Exception as exc:
                logger.warning("Config migration failed (continuing): %s", exc)

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
            return self._info
        except subprocess.TimeoutExpired:
            self._info.state = UpdateState.ERROR
            self._info.last_error = "Update command timed out"
            logger.error("Update apply timed out")
            return self._info
        except (OSError, tarfile.TarError) as exc:
            self._info.state = UpdateState.ERROR
            self._info.last_error = f"Update failed: {exc}"
            logger.error("Update apply failed: %s", exc)
            return self._info

    async def _fetch_latest_release(self) -> dict[str, Any]:
        """Fetch the latest release metadata from GitHub API.

        For the *stable* channel, uses ``/releases/latest`` (which excludes
        pre-releases).  For the *nightly* channel, lists recent releases and
        picks the newest one whose tag starts with ``nightly-``.
        """
        if self._config.channel == "nightly":
            url = f"{self._api_base}?per_page=20"
        else:
            url = f"{self._api_base}/latest"

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "pi-couch-hound"},
        )

        def _do_fetch() -> dict[str, Any]:
            with urllib.request.urlopen(request, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            if self._config.channel == "nightly":
                for release in data:
                    tag: str = release.get("tag_name", "")
                    if tag.startswith("nightly-"):
                        return release  # type: ignore[no-any-return]
                msg = "No nightly releases found"
                hdrs: Any = {}
                raise urllib.error.HTTPError(url, 404, msg, hdrs, None)

            return data  # type: ignore[no-any-return]

        return await asyncio.to_thread(_do_fetch)

    async def _download_release(self, url: str) -> str:
        """Download a release tarball to a temp file, return its path."""

        def _do_download() -> str:
            fd, path = tempfile.mkstemp(suffix=".tar.gz")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "pi-couch-hound"})
                with urllib.request.urlopen(request, timeout=300) as resp:
                    with os.fdopen(fd, "wb") as f:
                        shutil.copyfileobj(resp, f)
                return path
            except Exception:
                os.close(fd) if not os.path.exists(path) else os.unlink(path)
                raise

        return await asyncio.to_thread(_do_download)

    async def _extract_and_overlay(self, tarball_path: str) -> None:
        """Extract a release tarball and overlay files onto the install directory."""

        def _do_extract() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                with tarfile.open(tarball_path, "r:gz") as tar:
                    # Security: validate no path traversal in tar members
                    for member in tar.getmembers():
                        member_path = os.path.normpath(member.name)
                        if member_path.startswith("..") or os.path.isabs(member_path):
                            raise tarfile.TarError(
                                f"Refusing to extract path with traversal: {member.name}"
                            )
                    # The "data" filter additionally rejects links, devices, and
                    # any member escaping the destination directory.
                    tar.extractall(tmpdir, filter="data")  # noqa: S202

                # Find the extracted directory (e.g., pi-couch-hound-0.2.0/)
                extracted = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
                if len(extracted) != 1:
                    raise tarfile.TarError(
                        f"Expected one top-level directory in tarball, found {len(extracted)}"
                    )
                src_dir = extracted[0]

                # Overlay files, preserving user data
                for item in src_dir.iterdir():
                    if item.name in _PRESERVE:
                        continue
                    dest = self._install_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

        await asyncio.to_thread(_do_extract)

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
                and self._info.python_compatible
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
