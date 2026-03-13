"""Tests for events API endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.database import EventDatabase


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture
def events_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with a seeded event database."""
    app = create_app()

    with TestClient(app) as client:
        # Replace the database created by lifespan with a test-isolated one
        db = EventDatabase(path=tmp_path / "test_events.db")
        _run(db.init())
        app.state.event_db = db

        # Seed sample events
        now = datetime.now(tz=UTC)
        _run(
            db.insert_event(
                timestamp=(now - timedelta(hours=3)).isoformat(),
                confidence=0.75,
                label="dog",
                bbox=[0.1, 0.2, 0.3, 0.4],
                snapshot_path=None,
                actions_fired=["bark_alarm"],
            )
        )
        _run(
            db.insert_event(
                timestamp=(now - timedelta(hours=2)).isoformat(),
                confidence=0.85,
                label="dog",
                bbox=[0.2, 0.3, 0.5, 0.6],
                snapshot_path="snaps/img_002.jpg",
                actions_fired=["bark_alarm", "save_snap"],
            )
        )
        _run(
            db.insert_event(
                timestamp=(now - timedelta(hours=1)).isoformat(),
                confidence=0.92,
                label="dog",
                bbox=[0.3, 0.4, 0.6, 0.7],
                snapshot_path=None,
                actions_fired=["notify"],
            )
        )

        yield client

        _run(db.close())


@pytest.fixture
def empty_events_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with an empty event database."""
    app = create_app()

    with TestClient(app) as client:
        db = EventDatabase(path=tmp_path / "test_events.db")
        _run(db.init())
        app.state.event_db = db

        yield client

        _run(db.close())


# ── GET /api/events ──


def test_list_events(events_client: TestClient) -> None:
    response = events_client.get("/api/events")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["events"]) == 3


def test_list_events_empty(empty_events_client: TestClient) -> None:
    response = empty_events_client.get("/api/events")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["events"] == []


def test_list_events_pagination(events_client: TestClient) -> None:
    response = events_client.get("/api/events?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["total"] == 3
    # Should be the most recent event (highest confidence: 0.92)
    assert data["events"][0]["confidence"] == 0.92


def test_list_events_with_since(events_client: TestClient) -> None:
    since = (datetime.now(tz=UTC) - timedelta(hours=1, minutes=30)).isoformat()
    response = events_client.get(f"/api/events?since={since}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["events"][0]["confidence"] == 0.92


def test_list_events_with_until(events_client: TestClient) -> None:
    until = (datetime.now(tz=UTC) - timedelta(hours=2, minutes=30)).isoformat()
    response = events_client.get(f"/api/events?until={until}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["events"][0]["confidence"] == 0.75


# ── GET /api/events/{id} ──


def test_get_event_by_id(events_client: TestClient) -> None:
    response = events_client.get("/api/events/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["label"] == "dog"
    assert data["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert data["actions_fired"] == ["bark_alarm"]


def test_get_event_not_found(events_client: TestClient) -> None:
    response = events_client.get("/api/events/999")
    assert response.status_code == 404


# ── DELETE /api/events/{id} ──


def test_delete_event(events_client: TestClient) -> None:
    response = events_client.delete("/api/events/1")
    assert response.status_code == 204

    # Verify it's gone
    response = events_client.get("/api/events/1")
    assert response.status_code == 404


def test_delete_event_not_found(events_client: TestClient) -> None:
    response = events_client.delete("/api/events/999")
    assert response.status_code == 404


def test_delete_event_removes_snapshot(events_client: TestClient, tmp_path: Path) -> None:
    """Deleting an event should also remove its snapshot file."""
    snapshot = tmp_path / "test_snap.jpg"
    snapshot.write_bytes(b"fake jpeg")

    # Insert an event with a snapshot path
    db: EventDatabase = events_client.app.state.event_db  # type: ignore[union-attr]
    event_id = _run(
        db.insert_event(
            timestamp=datetime.now(tz=UTC).isoformat(),
            confidence=0.88,
            label="dog",
            bbox=[0.0, 0.0, 1.0, 1.0],
            snapshot_path=str(snapshot),
            actions_fired=[],
        )
    )

    response = events_client.delete(f"/api/events/{event_id}")
    assert response.status_code == 204
    assert not snapshot.exists()


# ── DELETE /api/events (bulk) ──


def test_bulk_delete_events(events_client: TestClient) -> None:
    before = (datetime.now(tz=UTC) - timedelta(hours=1, minutes=30)).isoformat()
    response = events_client.delete(f"/api/events?before={before}")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 2

    # Verify only the recent event remains
    list_resp = events_client.get("/api/events")
    assert list_resp.json()["total"] == 1


def test_bulk_delete_requires_before(events_client: TestClient) -> None:
    response = events_client.delete("/api/events")
    assert response.status_code == 422


# ── GET /api/events/stats ──


def test_get_stats(events_client: TestClient) -> None:
    response = events_client.get("/api/events/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_events"] == 3
    assert 0.75 <= data["avg_confidence"] <= 0.92
    assert data["peak_hour"] is not None
    assert isinstance(data["detections_per_hour"], dict)
    assert isinstance(data["detections_per_day"], dict)
    assert isinstance(data["confidence_distribution"], dict)
    assert len(data["confidence_distribution"]) > 0


def test_get_stats_empty(empty_events_client: TestClient) -> None:
    response = empty_events_client.get("/api/events/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_events"] == 0
    assert data["avg_confidence"] == 0.0
    assert data["peak_hour"] is None
    assert data["confidence_distribution"] == {}
