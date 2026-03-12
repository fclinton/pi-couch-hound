"""Snapshot serving endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots").resolve()


def _is_within(filepath: Path, base: Path) -> bool:
    """Check that *filepath* is strictly contained within *base*."""
    return filepath == base or base in filepath.parents


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    try:
        filepath = (SNAPSHOTS_DIR / filename).resolve(strict=False)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not _is_within(filepath, SNAPSHOTS_DIR):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path=filepath, media_type="image/jpeg")
