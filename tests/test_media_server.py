"""Tests for the media server."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from couch_hound.media_server import _create_media_app


@pytest.fixture
def client() -> TestClient:
    app = _create_media_app(main_port=8080, ssl_enabled=False)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def ssl_client() -> TestClient:
    app = _create_media_app(main_port=8080, ssl_enabled=True)
    return TestClient(app, raise_server_exceptions=False)


def test_serve_existing_file(client: TestClient, tmp_path: Path) -> None:
    audio = tmp_path / "alert.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    response = client.get(f"/media/{audio}")
    assert response.status_code == 200
    assert "audio" in response.headers.get("content-type", "")


def test_serve_missing_file(client: TestClient) -> None:
    response = client.get("/media//nonexistent/sound.wav")
    assert response.status_code == 404


def test_catch_all_redirects_http(client: TestClient) -> None:
    response = client.get("/some/other/path", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert ":8080" in location
    assert location.startswith("http://")


def test_catch_all_redirects_https(ssl_client: TestClient) -> None:
    response = ssl_client.get("/some/other/path", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert ":8080" in location
    assert location.startswith("https://")
