"""Tests for the media server."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from couch_hound.media_server import _create_media_app


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    """A media root containing one audio file and one non-audio file."""
    (tmp_path / "alert.mp3").write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    (tmp_path / "secret.txt").write_text("not audio")
    sub = tmp_path / "sounds"
    sub.mkdir()
    (sub / "bark.wav").write_bytes(b"RIFF" + b"\x00" * 100)
    return tmp_path


@pytest.fixture
def client(media_root: Path) -> TestClient:
    app = _create_media_app(main_port=8080, ssl_enabled=False, media_root=media_root)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def ssl_client(media_root: Path) -> TestClient:
    app = _create_media_app(main_port=8080, ssl_enabled=True, media_root=media_root)
    return TestClient(app, raise_server_exceptions=False)


def test_serve_existing_file(client: TestClient) -> None:
    response = client.get("/media/alert.mp3")
    assert response.status_code == 200
    assert "audio" in response.headers.get("content-type", "")


def test_serve_nested_file(client: TestClient) -> None:
    response = client.get("/media/sounds/bark.wav")
    assert response.status_code == 200
    assert "audio" in response.headers.get("content-type", "")


def test_serve_missing_file(client: TestClient) -> None:
    response = client.get("/media/nonexistent.wav")
    assert response.status_code == 404


def test_reject_non_audio_extension(client: TestClient) -> None:
    """A file inside the root with a non-audio extension is not served."""
    response = client.get("/media/secret.txt")
    assert response.status_code == 415


def test_reject_absolute_path_traversal(client: TestClient) -> None:
    """An absolute path outside the media root must not be served."""
    response = client.get("/media//etc/passwd")
    assert response.status_code in (404, 415)


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
