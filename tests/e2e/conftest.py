"""E2E test fixtures: live server + Playwright browser."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest

# Playwright imports are optional — skip entire module if not installed
pw = pytest.importorskip("playwright.sync_api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 15.0) -> None:
    """Block until the server responds on the given port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.3)
    msg = f"Server did not start on port {port} within {timeout}s"
    raise TimeoutError(msg)


@pytest.fixture(scope="session")
def built_frontend() -> None:
    """Build the frontend once per test session (skipped if dist/ already exists)."""
    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
        return
    subprocess.run(
        ["npm", "run", "build"],
        cwd=str(FRONTEND_DIR),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def live_server(tmp_path: Path, built_frontend: None) -> Generator[str, None, None]:
    """Start the FastAPI app on a random port, yield the base URL."""
    port = _free_port()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")  # empty config → defaults

    env = {
        "COUCH_HOUND_CONFIG": str(config_path),
        "PATH": subprocess.check_output(["bash", "-c", "echo $PATH"], text=True).strip(),
    }

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "couch_hound.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_server(port)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture
def page(
    live_server: str,
    browser: pw.Browser,  # type: ignore[name-defined]
) -> Generator[pw.Page, None, None]:  # type: ignore[name-defined]
    """Playwright page navigated to the live server."""
    p = browser.new_page()
    p.goto(live_server)
    yield p
    p.close()
