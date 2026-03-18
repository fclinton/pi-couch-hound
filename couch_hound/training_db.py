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
        await self._db.execute(_CREATE_EVENT_UNIQUE_INDEX)
        await self._db.commit()
        logger.info("Training database initialized at %s", self._path)

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
    ) -> int:
        """Insert a training sample and return its id."""
        assert self._db is not None
        cursor = await self._db.execute(
            "INSERT INTO training_samples"
            " (image_path, label, is_positive, bbox, confidence, source, source_event_id, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                image_path,
                label,
                int(is_positive),
                json.dumps(bbox) if bbox else None,
                confidence,
                source,
                source_event_id,
                notes,
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
        """Aggregate dataset statistics."""
        assert self._db is not None

        cursor = await self._db.execute("SELECT COUNT(*) FROM training_samples")
        row = await cursor.fetchone()
        assert row is not None
        total: int = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE is_positive = 1"
        )
        row = await cursor.fetchone()
        assert row is not None
        positive: int = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM training_samples WHERE is_positive = 0"
        )
        row = await cursor.fetchone()
        assert row is not None
        negative: int = row[0]

        cursor = await self._db.execute(
            "SELECT label, COUNT(*) as cnt FROM training_samples GROUP BY label ORDER BY cnt DESC"
        )
        by_label: dict[str, int] = {r["label"]: r["cnt"] for r in await cursor.fetchall()}

        cursor = await self._db.execute(
            "SELECT source, COUNT(*) as cnt FROM training_samples GROUP BY source ORDER BY cnt DESC"
        )
        by_source: dict[str, int] = {r["source"]: r["cnt"] for r in await cursor.fetchall()}

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "by_label": by_label,
            "by_source": by_source,
        }

    async def get_all_samples(self) -> list[dict[str, object]]:
        """Fetch all samples (for export)."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM training_samples ORDER BY created_at")
        rows = await cursor.fetchall()
        return [self._deserialize_row(r) for r in rows]
