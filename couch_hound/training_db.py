"""SQLite storage layer for training dataset samples."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_CREATE_SAMPLES_TABLE = """\
CREATE TABLE IF NOT EXISTS training_samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path    TEXT    NOT NULL,
    label         TEXT    NOT NULL,
    is_positive   INTEGER NOT NULL DEFAULT 1,
    bbox          TEXT,
    confidence    REAL,
    source        TEXT    NOT NULL DEFAULT 'manual',
    source_event_id INTEGER,
    notes         TEXT,
    status        TEXT    NOT NULL DEFAULT 'approved',
    reviewed_at   TEXT,
    created_at    TEXT    DEFAULT (datetime('now'))
);
"""

_CREATE_INDEX = """\
CREATE INDEX IF NOT EXISTS idx_samples_label ON training_samples(label);
"""

_CREATE_EVENT_UNIQUE_INDEX = """\
CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_source_event_id
ON training_samples(source_event_id) WHERE source_event_id IS NOT NULL;
"""

_CREATE_STATUS_INDEX = """\
CREATE INDEX IF NOT EXISTS idx_samples_status ON training_samples(status);
"""


class TrainingDatabase:
    """Async SQLite database for training dataset management."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("data/training.db")
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Open the database and create the schema if needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_SAMPLES_TABLE)
        await self._db.execute(_CREATE_INDEX)
        await self._deduplicate_event_samples()
        await self._db.execute(_CREATE_EVENT_UNIQUE_INDEX)
        await self._migrate_add_status_column()
        await self._db.execute(_CREATE_STATUS_INDEX)
        await self._db.commit()
        logger.info("Training database initialized at %s", self._path)

    async def _deduplicate_event_samples(self) -> None:
        """Remove duplicate samples for the same source_event_id, keeping the newest."""
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM training_samples WHERE id NOT IN ("
            "  SELECT MAX(id) FROM training_samples"
            "  WHERE source_event_id IS NOT NULL"
            "  GROUP BY source_event_id"
            ") AND source_event_id IS NOT NULL"
        )
        if cursor.rowcount:
            logger.warning(
                "Removed %d duplicate training samples during migration", cursor.rowcount
            )

    async def _migrate_add_status_column(self) -> None:
        """Add status and reviewed_at columns if missing (migration for existing DBs)."""
        assert self._db is not None
        cursor = await self._db.execute("PRAGMA table_info(training_samples)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "status" not in columns:
            await self._db.execute(
                "ALTER TABLE training_samples ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'"
            )
            logger.info("Migrated training_samples: added 'status' column")
        if "reviewed_at" not in columns:
            await self._db.execute("ALTER TABLE training_samples ADD COLUMN reviewed_at TEXT")
            logger.info("Migrated training_samples: added 'reviewed_at' column")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _deserialize_row(self, row: aiosqlite.Row) -> dict[str, object]:
        """Convert a database row to a dict."""
        return {
            "id": row["id"],
            "image_path": row["image_path"],
            "label": row["label"],
            "is_positive": bool(row["is_positive"]),
            "bbox": json.loads(row["bbox"]) if row["bbox"] else None,
            "confidence": row["confidence"],
            "source": row["source"],
            "source_event_id": row["source_event_id"],
            "notes": row["notes"],
            "status": row["status"],
            "reviewed_at": row["reviewed_at"],
            "created_at": row["created_at"],
        }

    async def insert_sample(
        self,
        image_path: str,
        label: str,
        *,
        is_positive: bool = True,
        bbox: list[float] | None = None,
        confidence: float | None = None,
        source: str = "manual",
        source_event_id: int | None = None,
        notes: str | None = None,
        status: str = "approved",
    ) -> int:
        """Insert a training sample and return its id."""
        assert self._db is not None
        cursor = await self._db.execute(
            "INSERT INTO training_samples"
            " (image_path, label, is_positive, bbox, confidence, source,"
            "  source_event_id, notes, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                image_path,
                label,
                int(is_positive),
                json.dumps(bbox) if bbox else None,
                confidence,
                source,
                source_event_id,
                notes,
                status,
            ),
        )
        await self._db.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def get_sample_by_event_id(self, event_id: int) -> dict[str, object] | None:
        """Fetch a training sample linked to a specific event, if any."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM training_samples WHERE source_event_id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_row(row)

    async def get_samples_by_event_ids(self, event_ids: list[int]) -> dict[int, dict[str, object]]:
        """Fetch training samples for multiple event IDs. Returns {event_id: sample}."""
        if not event_ids:
            return {}
        assert self._db is not None
        placeholders = ",".join("?" for _ in event_ids)
        cursor = await self._db.execute(
            f"SELECT * FROM training_samples WHERE source_event_id IN ({placeholders})",  # noqa: S608
            event_ids,
        )
        rows = await cursor.fetchall()
        return {
            int(str(row["source_event_id"])): self._deserialize_row(row)
            for row in rows
            if row["source_event_id"] is not None
        }

    async def get_sample(self, sample_id: int) -> dict[str, object] | None:
        """Fetch a single sample by id."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM training_samples WHERE id = ?", (sample_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_row(row)

    async def list_samples(
        self,
        limit: int = 50,
        offset: int = 0,
        label: str | None = None,
        is_positive: bool | None = None,
        source: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        """Paginated sample listing with optional filters."""
        assert self._db is not None
        conditions: list[str] = []
        params: list[object] = []

        if label is not None:
            conditions.append("label = ?")
            params.append(label)
        if is_positive is not None:
            conditions.append("is_positive = ?")
            params.append(int(is_positive))
        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) FROM training_samples{where}",
            params,  # noqa: S608
        )
        count_row = await count_cursor.fetchone()
        assert count_row is not None
        total: int = count_row[0]

        query = (
            f"SELECT * FROM training_samples{where}"  # noqa: S608
            " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        cursor = await self._db.execute(query, [*params, limit, offset])
        rows = await cursor.fetchall()

        return [self._deserialize_row(r) for r in rows], total

    async def update_sample(
        self,
        sample_id: int,
        *,
        label: str | None = None,
        is_positive: bool | None = None,
        bbox: list[float] | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> dict[str, object] | None:
        """Update fields on a sample. Returns updated sample or None."""
        assert self._db is not None

        # Check sample exists
        existing = await self.get_sample(sample_id)
        if existing is None:
            return None

        updates: list[str] = []
        params: list[object] = []
        if label is not None:
            updates.append("label = ?")
            params.append(label)
        if is_positive is not None:
            updates.append("is_positive = ?")
            params.append(int(is_positive))
        if bbox is not None:
            updates.append("bbox = ?")
            params.append(json.dumps(bbox))
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status in ("approved", "rejected") and existing["status"] == "pending":
                updates.append("reviewed_at = datetime('now')")

        if not updates:
            return existing

        params.append(sample_id)
        await self._db.execute(
            f"UPDATE training_samples SET {', '.join(updates)} WHERE id = ?",  # noqa: S608
            params,
        )
        await self._db.commit()
        return await self.get_sample(sample_id)

    async def delete_sample(self, sample_id: int) -> dict[str, object] | None:
        """Delete a sample. Returns the deleted row or None."""
        assert self._db is not None
        sample = await self.get_sample(sample_id)
        if sample is None:
            return None
        await self._db.execute("DELETE FROM training_samples WHERE id = ?", (sample_id,))
        await self._db.commit()
        return sample

    async def get_stats(self) -> dict[str, object]:
        """Aggregate dataset statistics (only counts approved samples)."""
        assert self._db is not None

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE status = 'approved'"
        )
        row = await cursor.fetchone()
        assert row is not None
        total: int = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE is_positive = 1 AND status = 'approved'"
        )
        row = await cursor.fetchone()
        assert row is not None
        positive: int = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE is_positive = 0 AND status = 'approved'"
        )
        row = await cursor.fetchone()
        assert row is not None
        negative: int = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE status = 'pending'"
        )
        row = await cursor.fetchone()
        assert row is not None
        pending: int = row[0]

        cursor = await self._db.execute(
            "SELECT label, COUNT(*) as cnt FROM training_samples"
            " WHERE status = 'approved' GROUP BY label ORDER BY cnt DESC"
        )
        by_label: dict[str, int] = {r["label"]: r["cnt"] for r in await cursor.fetchall()}

        cursor = await self._db.execute(
            "SELECT source, COUNT(*) as cnt FROM training_samples"
            " WHERE status = 'approved' GROUP BY source ORDER BY cnt DESC"
        )
        by_source: dict[str, int] = {r["source"]: r["cnt"] for r in await cursor.fetchall()}

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "pending": pending,
            "by_label": by_label,
            "by_source": by_source,
        }

    async def get_all_samples(self) -> list[dict[str, object]]:
        """Fetch all approved samples (for export)."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM training_samples WHERE status = 'approved' ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [self._deserialize_row(r) for r in rows]

    async def review_sample(self, sample_id: int, status: str) -> dict[str, object] | None:
        """Set sample status to approved or rejected. Returns updated sample or None."""
        if status not in ("approved", "rejected"):
            msg = f"Invalid review status: {status}"
            raise ValueError(msg)
        return await self.update_sample(sample_id, status=status)
