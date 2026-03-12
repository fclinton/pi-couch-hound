"""Snapshot serving endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots").resolve()


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    filepath = (SNAPSHOTS_DIR / filename).resolve()
    if not filepath.is_relative_to(SNAPSHOTS_DIR):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path=filepath, media_type="image/jpeg")
