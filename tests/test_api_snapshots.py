"""Tests for snapshot serving API endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from couch_hound.api.app import create_app


def test_get_snapshot_success(tmp_path: Path) -> None:
    """GET /api/snapshots/{filename} serves a snapshot image."""
    jpeg_data = b"\xff\xd8\xff\xe0fake_jpeg_content"
    (tmp_path / "detection_001.jpg").write_bytes(jpeg_data)

    with patch("couch_hound.api.routes_snapshots.SNAPSHOTS_DIR", tmp_path):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/snapshots/detection_001.jpg")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.content == jpeg_data


def test_get_snapshot_not_found() -> None:
    """GET /api/snapshots/{filename} returns 404 for missing files."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/snapshots/nonexistent.jpg")
        assert response.status_code == 404
        assert response.json()["detail"] == "Snapshot not found"


def test_get_snapshot_path_traversal() -> None:
    """GET /api/snapshots/{filename} rejects path traversal attempts."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/snapshots/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (400, 404)  # rejected either way


def test_get_snapshot_dotdot_rejected() -> None:
    """GET /api/snapshots/{filename} rejects filenames with '..'."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/snapshots/..config.yaml")
        assert response.status_code == 400
