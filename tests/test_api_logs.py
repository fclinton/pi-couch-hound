"""Tests for logs API endpoint."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import AppConfig, LoggingConfig


@pytest.fixture
def logs_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with a custom log file path."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config = AppConfig(logging=LoggingConfig(file=str(tmp_path / "test.log")))
        yield client


def test_get_logs_missing_file(logs_client: TestClient) -> None:
    """GET /api/logs returns empty when log file does not exist."""
    response = logs_client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["entries"] == []
    assert data["total_lines"] == 0
    assert data["returned"] == 0


def test_get_logs_parses_entries(logs_client: TestClient, tmp_path: Path) -> None:
    """GET /api/logs parses structured log entries correctly."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2026-03-18 10:00:00 INFO     [couch_hound.api] Server started\n"
        "2026-03-18 10:00:01 WARNING  [couch_hound.pipeline] Low confidence\n"
    )

    response = logs_client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["returned"] == 2
    assert data["total_lines"] == 2
    assert data["entries"][0]["timestamp"] == "2026-03-18 10:00:00"
    assert data["entries"][0]["level"] == "INFO"
    assert data["entries"][0]["logger"] == "couch_hound.api"
    assert data["entries"][0]["message"] == "Server started"
    assert data["entries"][1]["level"] == "WARNING"


def test_get_logs_lines_param(logs_client: TestClient, tmp_path: Path) -> None:
    """GET /api/logs?lines=N limits the number of returned entries."""
    log_file = tmp_path / "test.log"
    lines = [f"2026-03-18 10:00:{i:02d} INFO     [test] Line {i}\n" for i in range(20)]
    log_file.write_text("".join(lines))

    response = logs_client.get("/api/logs?lines=5")
    assert response.status_code == 200
    data = response.json()
    assert data["returned"] == 5
    assert data["total_lines"] == 20
    # Should be the last 5 entries
    assert data["entries"][0]["message"] == "Line 15"
    assert data["entries"][4]["message"] == "Line 19"


def test_get_logs_level_filter(logs_client: TestClient, tmp_path: Path) -> None:
    """GET /api/logs?level=ERROR filters entries by level."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2026-03-18 10:00:00 INFO     [test] Info message\n"
        "2026-03-18 10:00:01 ERROR    [test] Error message\n"
        "2026-03-18 10:00:02 INFO     [test] Another info\n"
        "2026-03-18 10:00:03 ERROR    [test] Another error\n"
    )

    response = logs_client.get("/api/logs?level=ERROR")
    assert response.status_code == 200
    data = response.json()
    assert data["returned"] == 2
    assert all(e["level"] == "ERROR" for e in data["entries"])


def test_get_logs_multiline_traceback(logs_client: TestClient, tmp_path: Path) -> None:
    """Continuation lines (tracebacks) are appended to the previous entry."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2026-03-18 10:00:00 ERROR    [test] Something failed\n"
        "Traceback (most recent call last):\n"
        '  File "main.py", line 1, in <module>\n'
        "RuntimeError: boom\n"
        "2026-03-18 10:00:01 INFO     [test] Recovery\n"
    )

    response = logs_client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["returned"] == 2
    assert "Traceback" in data["entries"][0]["message"]
    assert "RuntimeError: boom" in data["entries"][0]["message"]
    assert data["entries"][1]["message"] == "Recovery"
