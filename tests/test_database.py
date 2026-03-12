"""Unit tests for the EventDatabase layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from couch_hound.database import EventDatabase


@pytest.fixture
async def db(tmp_path: Path) -> EventDatabase:
    """Create and initialize a test database."""
    event_db = EventDatabase(path=tmp_path / "test_events.db")
    await event_db.init()
    yield event_db  # type: ignore[misc]
    await event_db.close()


async def _insert_sample(
    db: EventDatabase,
    timestamp: str | None = None,
    confidence: float = 0.85,
    label: str = "dog",
) -> int:
    """Insert a sample event and return its id."""
    ts = timestamp or datetime.now(tz=UTC).isoformat()
    return await db.insert_event(
        timestamp=ts,
        confidence=confidence,
        label=label,
        bbox=[0.1, 0.2, 0.3, 0.4],
        snapshot_path=None,
        actions_fired=["bark_alarm"],
    )


# ── insert & get ──


async def test_insert_and_get(db: EventDatabase) -> None:
    event_id = await _insert_sample(db, confidence=0.92)
    event = await db.get_event(event_id)
    assert event is not None
    assert event["id"] == event_id
    assert event["confidence"] == 0.92
    assert event["label"] == "dog"
    assert event["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert event["actions_fired"] == ["bark_alarm"]


async def test_get_nonexistent(db: EventDatabase) -> None:
    result = await db.get_event(999)
    assert result is None


async def test_insert_with_snapshot_path(db: EventDatabase) -> None:
    event_id = await db.insert_event(
        timestamp=datetime.now(tz=UTC).isoformat(),
        confidence=0.75,
        label="dog",
        bbox=[0.5, 0.5, 0.8, 0.8],
        snapshot_path="snapshots/img_001.jpg",
        actions_fired=["save_snap", "notify"],
    )
    event = await db.get_event(event_id)
    assert event is not None
    assert event["snapshot_path"] == "snapshots/img_001.jpg"
    assert event["actions_fired"] == ["save_snap", "notify"]


# ── list events ──


async def test_list_events_empty(db: EventDatabase) -> None:
    events, total = await db.list_events()
    assert events == []
    assert total == 0


async def test_list_events_pagination(db: EventDatabase) -> None:
    for i in range(5):
        await _insert_sample(db, confidence=0.5 + i * 0.1)

    events, total = await db.list_events(limit=2, offset=0)
    assert len(events) == 2
    assert total == 5

    events2, total2 = await db.list_events(limit=2, offset=2)
    assert len(events2) == 2
    assert total2 == 5

    events3, total3 = await db.list_events(limit=2, offset=4)
    assert len(events3) == 1
    assert total3 == 5


async def test_list_events_ordered_by_timestamp_desc(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    t1 = (now - timedelta(hours=2)).isoformat()
    t2 = (now - timedelta(hours=1)).isoformat()
    t3 = now.isoformat()

    await _insert_sample(db, timestamp=t1)
    await _insert_sample(db, timestamp=t3)
    await _insert_sample(db, timestamp=t2)

    events, _ = await db.list_events()
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == [t3, t2, t1]


async def test_list_events_since_filter(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    old = (now - timedelta(hours=5)).isoformat()
    recent = now.isoformat()
    cutoff = (now - timedelta(hours=1)).isoformat()

    await _insert_sample(db, timestamp=old)
    await _insert_sample(db, timestamp=recent)

    events, total = await db.list_events(since=cutoff)
    assert total == 1
    assert events[0]["timestamp"] == recent


async def test_list_events_until_filter(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    old = (now - timedelta(hours=5)).isoformat()
    recent = now.isoformat()
    cutoff = (now - timedelta(hours=1)).isoformat()

    await _insert_sample(db, timestamp=old)
    await _insert_sample(db, timestamp=recent)

    events, total = await db.list_events(until=cutoff)
    assert total == 1
    assert events[0]["timestamp"] == old


# ── delete ──


async def test_delete_event(db: EventDatabase) -> None:
    event_id = await _insert_sample(db)
    deleted = await db.delete_event(event_id)
    assert deleted is not None
    assert deleted["id"] == event_id

    assert await db.get_event(event_id) is None


async def test_delete_nonexistent(db: EventDatabase) -> None:
    result = await db.delete_event(999)
    assert result is None


async def test_bulk_delete(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    old1 = (now - timedelta(hours=5)).isoformat()
    old2 = (now - timedelta(hours=3)).isoformat()
    recent = now.isoformat()

    await _insert_sample(db, timestamp=old1)
    await _insert_sample(db, timestamp=old2)
    await _insert_sample(db, timestamp=recent)

    cutoff = (now - timedelta(hours=1)).isoformat()
    count, paths = await db.bulk_delete_events(cutoff)
    assert count == 2
    assert paths == []  # no snapshots

    events, total = await db.list_events()
    assert total == 1
    assert events[0]["timestamp"] == recent


async def test_bulk_delete_returns_snapshot_paths(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    old = (now - timedelta(hours=2)).isoformat()
    await db.insert_event(
        timestamp=old,
        confidence=0.9,
        label="dog",
        bbox=[0.1, 0.2, 0.3, 0.4],
        snapshot_path="snaps/old.jpg",
        actions_fired=[],
    )
    count, paths = await db.bulk_delete_events(now.isoformat())
    assert count == 1
    assert paths == ["snaps/old.jpg"]


# ── stats ──


async def test_stats_empty(db: EventDatabase) -> None:
    stats = await db.get_stats()
    assert stats["total_events"] == 0
    assert stats["avg_confidence"] == 0.0
    assert stats["detections_per_hour"] == {}
    assert stats["detections_per_day"] == {}
    assert stats["peak_hour"] is None


async def test_stats_with_data(db: EventDatabase) -> None:
    now = datetime.now(tz=UTC)
    for i in range(3):
        ts = (now - timedelta(hours=i)).isoformat()
        await _insert_sample(db, timestamp=ts, confidence=0.8 + i * 0.05)

    stats = await db.get_stats()
    assert stats["total_events"] == 3
    assert 0.8 <= stats["avg_confidence"] <= 0.95
    assert stats["peak_hour"] is not None
    assert len(stats["detections_per_hour"]) > 0
    assert len(stats["detections_per_day"]) > 0


# ── database file creation ──


async def test_creates_parent_directories(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "events.db"
    event_db = EventDatabase(path=db_path)
    await event_db.init()
    assert db_path.exists()
    await event_db.close()
