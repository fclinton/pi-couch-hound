"""Snapshot serving endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots")


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = SNAPSHOTS_DIR / safe_name
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    resolved = filepath.resolve()
    if not resolved.is_relative_to(SNAPSHOTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")

    return FileResponse(path=resolved, media_type="image/jpeg")
