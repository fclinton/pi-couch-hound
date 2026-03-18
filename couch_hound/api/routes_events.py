"""Events endpoints — paginated listing, detail, delete, bulk delete, and stats."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response

from couch_hound.api.schemas import (
    EventListResponse,
    EventResponse,
    EventStatsResponse,
    EventTrainingInfo,
)
from couch_hound.database import EventDatabase
from couch_hound.training_db import TrainingDatabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


def _get_db(request: Request) -> EventDatabase:
    """Retrieve the event database from app state."""
    db: EventDatabase | None = request.app.state.event_db
    if db is None:
        raise HTTPException(status_code=503, detail="Event database unavailable")
    return db


def _get_training_db(request: Request) -> TrainingDatabase | None:
    """Retrieve the training database from app state (may not be available)."""
    return getattr(request.app.state, "training_db", None)


def _make_training_info(sample: dict[str, object]) -> EventTrainingInfo:
    return EventTrainingInfo(
        sample_id=int(str(sample["id"])),
        label=str(sample["label"]),
        is_positive=bool(sample["is_positive"]),
    )


@router.get("/events/stats")
async def get_event_stats(request: Request) -> EventStatsResponse:
    """Aggregate detection statistics."""
    db = _get_db(request)
    stats = await db.get_stats()
    return EventStatsResponse(**stats)


@router.get("/events")
async def list_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
) -> EventListResponse:
    """Paginated event listing with optional timestamp filters."""
    db = _get_db(request)
    events, total = await db.list_events(limit=limit, offset=offset, since=since, until=until)

    training_db = _get_training_db(request)
    training_map: dict[int, dict[str, object]] = {}
    if training_db is not None:
        event_ids = [int(str(e["id"])) for e in events]
        training_map = await training_db.get_samples_by_event_ids(event_ids)

    response_events = []
    for e in events:
        eid = int(str(e["id"]))
        training = _make_training_info(training_map[eid]) if eid in training_map else None
        response_events.append(EventResponse(**e, training=training))

    return EventListResponse(
        events=response_events,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}")
async def get_event(event_id: int, request: Request) -> EventResponse:
    """Get a single event by id."""
    db = _get_db(request)
    event = await db.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    training: EventTrainingInfo | None = None
    training_db = _get_training_db(request)
    if training_db is not None:
        sample = await training_db.get_sample_by_event_id(event_id)
        if sample is not None:
            training = _make_training_info(sample)

    return EventResponse(**event, training=training)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: int, request: Request) -> Response:
    """Delete a single event and its snapshot file."""
    db = _get_db(request)
    deleted = await db.delete_event(event_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    snapshot_path = deleted.get("snapshot_path")
    if snapshot_path is not None:
        p = Path(str(snapshot_path))
        if p.is_file():
            try:
                p.unlink()
                logger.info("Deleted snapshot %s", p)
            except OSError:
                logger.warning("Failed to delete snapshot %s", p, exc_info=True)

    return Response(status_code=204)


@router.delete("/events")
async def bulk_delete_events(
    request: Request,
    before: str = Query(...),
) -> dict[str, int]:
    """Bulk delete events before a timestamp."""
    db = _get_db(request)
    count, snapshot_paths = await db.bulk_delete_events(before)

    for sp in snapshot_paths:
        p = Path(sp)
        if p.is_file():
            try:
                p.unlink()
                logger.info("Deleted snapshot %s", p)
            except OSError:
                logger.warning("Failed to delete snapshot %s", p, exc_info=True)

    return {"deleted": count}
