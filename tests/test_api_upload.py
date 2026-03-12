"""Tests for file upload and listing API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import AppConfig


@pytest.fixture
def upload_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    """Return a test client with working directory set to tmp_path."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig()
        yield client


# ── POST /api/upload/sound ──


def test_upload_sound_wav(upload_client: TestClient) -> None:
    files = {"file": ("bark.wav", BytesIO(b"fake-wav-data"), "audio/wav")}
    response = upload_client.post("/api/upload/sound", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "bark.wav"
    assert data["path"] == "sounds/bark.wav"
    assert data["size"] == len(b"fake-wav-data")


def test_upload_sound_mp3(upload_client: TestClient) -> None:
    files = {"file": ("alert.mp3", BytesIO(b"fake-mp3-data"), "audio/mpeg")}
    response = upload_client.post("/api/upload/sound", files=files)
    assert response.status_code == 201
    assert response.json()["filename"] == "alert.mp3"


def test_upload_sound_invalid_extension(upload_client: TestClient) -> None:
    files = {"file": ("malware.exe", BytesIO(b"bad"), "application/octet-stream")}
    response = upload_client.post("/api/upload/sound", files=files)
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_sound_too_large(upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import couch_hound.api.routes_upload as routes_mod

    monkeypatch.setattr(routes_mod, "MAX_SOUND_SIZE", 10)
    files = {"file": ("big.wav", BytesIO(b"x" * 20), "audio/wav")}
    response = upload_client.post("/api/upload/sound", files=files)
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_upload_sound_path_traversal(upload_client: TestClient) -> None:
    files = {"file": ("../../etc/passwd", BytesIO(b"data"), "audio/wav")}
    response = upload_client.post("/api/upload/sound", files=files)
    # Path.name strips directory components, so "passwd" has no valid audio extension
    assert response.status_code == 400


def test_upload_sound_empty_filename(upload_client: TestClient) -> None:
    files = {"file": ("", BytesIO(b"data"), "audio/wav")}
    response = upload_client.post("/api/upload/sound", files=files)
    assert response.status_code in (400, 422)


def test_upload_sound_overwrites_existing(upload_client: TestClient, tmp_path: Path) -> None:
    files1 = {"file": ("test.wav", BytesIO(b"first"), "audio/wav")}
    upload_client.post("/api/upload/sound", files=files1)

    files2 = {"file": ("test.wav", BytesIO(b"second-content"), "audio/wav")}
    response = upload_client.post("/api/upload/sound", files=files2)
    assert response.status_code == 201
    assert response.json()["size"] == len(b"second-content")

    # Verify file on disk has new content
    assert (tmp_path / "sounds" / "test.wav").read_bytes() == b"second-content"


# ── POST /api/upload/model ──


def test_upload_model_valid(upload_client: TestClient) -> None:
    files = {
        "model": ("custom.tflite", BytesIO(b"tflite-data"), "application/octet-stream"),
        "labels": ("custom.txt", BytesIO(b"dog\ncat\n"), "text/plain"),
    }
    response = upload_client.post("/api/upload/model", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["model"] == "models/custom.tflite"
    assert data["labels"] == "models/custom.txt"


def test_upload_model_wrong_model_extension(upload_client: TestClient) -> None:
    files = {
        "model": ("model.pb", BytesIO(b"data"), "application/octet-stream"),
        "labels": ("labels.txt", BytesIO(b"labels"), "text/plain"),
    }
    response = upload_client.post("/api/upload/model", files=files)
    assert response.status_code == 400
    assert ".tflite" in response.json()["detail"]


def test_upload_model_wrong_labels_extension(upload_client: TestClient) -> None:
    files = {
        "model": ("model.tflite", BytesIO(b"data"), "application/octet-stream"),
        "labels": ("labels.csv", BytesIO(b"labels"), "text/csv"),
    }
    response = upload_client.post("/api/upload/model", files=files)
    assert response.status_code == 400
    assert ".txt" in response.json()["detail"]


def test_upload_model_too_large(upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import couch_hound.api.routes_upload as routes_mod

    monkeypatch.setattr(routes_mod, "MAX_MODEL_SIZE", 10)
    files = {
        "model": ("big.tflite", BytesIO(b"x" * 20), "application/octet-stream"),
        "labels": ("labels.txt", BytesIO(b"labels"), "text/plain"),
    }
    response = upload_client.post("/api/upload/model", files=files)
    assert response.status_code == 413


# ── GET /api/sounds ──


def test_list_sounds_empty(upload_client: TestClient) -> None:
    response = upload_client.get("/api/sounds")
    assert response.status_code == 200
    assert response.json()["sounds"] == []


def test_list_sounds_with_files(upload_client: TestClient, tmp_path: Path) -> None:
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    (sounds_dir / "bark.wav").write_bytes(b"wav-data")
    (sounds_dir / "alert.mp3").write_bytes(b"mp3-data")

    response = upload_client.get("/api/sounds")
    assert response.status_code == 200
    sounds = response.json()["sounds"]
    assert len(sounds) == 2
    filenames = [s["filename"] for s in sounds]
    assert "bark.wav" in filenames
    assert "alert.mp3" in filenames


def test_list_sounds_ignores_non_audio(upload_client: TestClient, tmp_path: Path) -> None:
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    (sounds_dir / "notes.txt").write_bytes(b"not audio")
    (sounds_dir / "good.wav").write_bytes(b"audio")

    response = upload_client.get("/api/sounds")
    sounds = response.json()["sounds"]
    assert len(sounds) == 1
    assert sounds[0]["filename"] == "good.wav"


# ── GET /api/models ──


def test_list_models_empty(upload_client: TestClient) -> None:
    response = upload_client.get("/api/models")
    assert response.status_code == 200
    assert response.json()["models"] == []


def test_list_models_with_labels(upload_client: TestClient, tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "ssd.tflite").write_bytes(b"model-data")
    (models_dir / "ssd.txt").write_bytes(b"dog\ncat\n")

    response = upload_client.get("/api/models")
    models = response.json()["models"]
    assert len(models) == 1
    assert models[0]["filename"] == "ssd.tflite"
    assert models[0]["labels"] == "models/ssd.txt"


def test_list_models_without_labels(upload_client: TestClient, tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "custom.tflite").write_bytes(b"model-data")

    response = upload_client.get("/api/models")
    models = response.json()["models"]
    assert len(models) == 1
    assert models[0]["labels"] is None


# ── Integration: upload then list ──


def test_upload_then_list_sound(upload_client: TestClient) -> None:
    files = {"file": ("new.wav", BytesIO(b"wav-content"), "audio/wav")}
    upload_client.post("/api/upload/sound", files=files)

    response = upload_client.get("/api/sounds")
    sounds = response.json()["sounds"]
    assert len(sounds) == 1
    assert sounds[0]["filename"] == "new.wav"
    assert sounds[0]["size"] == len(b"wav-content")


def test_upload_then_list_model(upload_client: TestClient) -> None:
    files = {
        "model": ("detect.tflite", BytesIO(b"model"), "application/octet-stream"),
        "labels": ("detect.txt", BytesIO(b"labels"), "text/plain"),
    }
    upload_client.post("/api/upload/model", files=files)

    response = upload_client.get("/api/models")
    models = response.json()["models"]
    assert len(models) == 1
    assert models[0]["filename"] == "detect.tflite"
    assert models[0]["labels"] == "models/detect.txt"
