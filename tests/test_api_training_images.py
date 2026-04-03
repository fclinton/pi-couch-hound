"""Tests for training image serving endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from couch_hound.api.app import create_app


def test_serve_image_from_training_images(tmp_path: Path) -> None:
    """Image in data/training_images/ is served correctly."""
    training_dir = tmp_path / "training_images"
    training_dir.mkdir()
    crops_dir = tmp_path / "training_crops"
    crops_dir.mkdir()

    jpeg_data = b"\xff\xd8\xff\xe0fake_jpeg"
    (training_dir / "upload_123.jpg").write_bytes(jpeg_data)

    with patch(
        "couch_hound.api.routes_training._IMAGE_DIRS",
        [training_dir.resolve(), crops_dir.resolve()],
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/training/images/upload_123.jpg")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"
            assert resp.content == jpeg_data


def test_serve_image_from_training_crops(tmp_path: Path) -> None:
    """Image in data/training_crops/ is served correctly (the bug fix)."""
    training_dir = tmp_path / "training_images"
    training_dir.mkdir()
    crops_dir = tmp_path / "training_crops"
    crops_dir.mkdir()

    jpeg_data = b"\xff\xd8\xff\xe0crop_jpeg"
    (crops_dir / "crop_pos_dog_0.85_20260402_235122_123456.jpg").write_bytes(jpeg_data)

    with patch(
        "couch_hound.api.routes_training._IMAGE_DIRS",
        [training_dir.resolve(), crops_dir.resolve()],
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/training/images/crop_pos_dog_0.85_20260402_235122_123456.jpg")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"
            assert resp.content == jpeg_data


def test_serve_image_not_found(tmp_path: Path) -> None:
    """Missing file returns 404."""
    training_dir = tmp_path / "training_images"
    training_dir.mkdir()
    crops_dir = tmp_path / "training_crops"
    crops_dir.mkdir()

    with patch(
        "couch_hound.api.routes_training._IMAGE_DIRS",
        [training_dir.resolve(), crops_dir.resolve()],
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/training/images/nonexistent.jpg")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Image not found"


def test_serve_image_path_traversal_rejected(tmp_path: Path) -> None:
    """Path traversal attempts are rejected."""
    training_dir = tmp_path / "training_images"
    training_dir.mkdir()
    crops_dir = tmp_path / "training_crops"
    crops_dir.mkdir()
    (tmp_path / "secret.txt").write_bytes(b"secret")

    with patch(
        "couch_hound.api.routes_training._IMAGE_DIRS",
        [training_dir.resolve(), crops_dir.resolve()],
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/training/images/..%2Fsecret.txt")
            assert resp.status_code in (400, 404)
