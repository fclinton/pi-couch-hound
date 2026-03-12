"""SQLite event storage layer for detection events."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    confidence    REAL    NOT NULL,
    label         TEXT    NOT NULL,
    bbox          TEXT    NOT NULL,
    snapshot_path TEXT,
    actions_fired TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);
"""

_CREATE_INDEX = """\
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


class EventDatabase:
    """Async SQLite database for detection event persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("data/events.db")
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Open the database and create the schema if needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE)
        await self._db.execute(_CREATE_INDEX)
        await self._db.commit()
        logger.info("Event database initialized at %s", self._path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _deserialize_row(self, row: aiosqlite.Row) -> dict[str, object]:
        """Convert a database row to a dict with deserialized JSON fields."""
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "confidence": row["confidence"],
            "label": row["label"],
            "bbox": json.loads(row["bbox"]),
            "snapshot_path": row["snapshot_path"],
            "actions_fired": json.loads(row["actions_fired"]),
        }

    async def insert_event(
        self,
        timestamp: str,
        confidence: float,
        label: str,
        bbox: list[float],
        snapshot_path: str | None,
        actions_fired: list[str],
    ) -> int:
        """Insert a detection event and return its id."""
        assert self._db is not None
        cursor = await self._db.execute(
            "INSERT INTO events (timestamp, confidence, label, bbox, snapshot_path, actions_fired)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                timestamp,
                confidence,
                label,
                json.dumps(bbox),
                snapshot_path,
                json.dumps(actions_fired),
            ),
        )
        await self._db.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def get_event(self, event_id: int) -> dict[str, object] | None:
        """Fetch a single event by id."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_row(row)

    async def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        since: str | None = None,
        until: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        """Paginated event listing with optional timestamp filters."""
        assert self._db is not None
        conditions: list[str] = []
        params: list[object] = []

        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cursor = await self._db.execute(f"SELECT COUNT(*) FROM events{where}", params)
        count_row = await count_cursor.fetchone()
        assert count_row is not None
        total: int = count_row[0]

        query = f"SELECT * FROM events{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"  # noqa: S608
        cursor = await self._db.execute(query, [*params, limit, offset])
        rows = await cursor.fetchall()

        return [self._deserialize_row(r) for r in rows], total

    async def delete_event(self, event_id: int) -> dict[str, object] | None:
        """Delete a single event. Returns the deleted row or None."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        result = self._deserialize_row(row)
        await self._db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        await self._db.commit()
        return result

    async def bulk_delete_events(self, before: str) -> tuple[int, list[str]]:
        """Delete events before a timestamp. Returns (count, snapshot_paths)."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT snapshot_path FROM events WHERE timestamp < ?", (before,)
        )
        rows = await cursor.fetchall()
        paths = [r["snapshot_path"] for r in rows if r["snapshot_path"] is not None]

        delete_cursor = await self._db.execute("DELETE FROM events WHERE timestamp < ?", (before,))
        await self._db.commit()
        deleted = delete_cursor.rowcount
        return deleted, paths

    async def get_stats(self) -> dict[str, object]:
        """Aggregate detection statistics."""
        assert self._db is not None

        # Total events and average confidence
        cursor = await self._db.execute(
            "SELECT COUNT(*) as total, COALESCE(AVG(confidence), 0.0) as avg_conf FROM events"
        )
        row = await cursor.fetchone()
        assert row is not None
        total_events: int = row["total"]
        avg_confidence: float = round(row["avg_conf"], 4)

        # Detections per hour (last 24h)
        now = datetime.now(tz=UTC)
        since_24h = (now - timedelta(hours=24)).isoformat()
        cursor = await self._db.execute(
            "SELECT strftime('%Y-%m-%dT%H', timestamp) as hour, COUNT(*) as cnt"
            " FROM events WHERE timestamp >= ? GROUP BY hour ORDER BY hour",
            (since_24h,),
        )
        per_hour: dict[str, int] = {r["hour"]: r["cnt"] for r in await cursor.fetchall()}

        # Detections per day (last 7 days)
        since_7d = (now - timedelta(days=7)).isoformat()
        cursor = await self._db.execute(
            "SELECT strftime('%Y-%m-%d', timestamp) as day, COUNT(*) as cnt"
            " FROM events WHERE timestamp >= ? GROUP BY day ORDER BY day",
            (since_7d,),
        )
        per_day: dict[str, int] = {r["day"]: r["cnt"] for r in await cursor.fetchall()}

        # Peak hour (0-23) across all events
        cursor = await self._db.execute(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hr, COUNT(*) as cnt"
            " FROM events GROUP BY hr ORDER BY cnt DESC LIMIT 1"
        )
        peak_row = await cursor.fetchone()
        peak_hour: int | None = peak_row["hr"] if peak_row is not None else None

        return {
            "total_events": total_events,
            "avg_confidence": avg_confidence,
            "detections_per_hour": per_hour,
            "detections_per_day": per_day,
            "peak_hour": peak_hour,
        }
