"""Events endpoints — paginated listing, detail, delete, bulk delete, and stats."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response

from couch_hound.api.schemas import EventListResponse, EventResponse, EventStatsResponse
from couch_hound.database import EventDatabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


def _get_db(request: Request) -> EventDatabase:
    """Retrieve the event database from app state."""
    db: EventDatabase = request.app.state.event_db
    return db


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
    return EventListResponse(
        events=[EventResponse(**e) for e in events],
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
    return EventResponse(**event)


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
            p.unlink()
            logger.info("Deleted snapshot %s", p)

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
            p.unlink()
            logger.info("Deleted snapshot %s", p)

    return {"deleted": count}
