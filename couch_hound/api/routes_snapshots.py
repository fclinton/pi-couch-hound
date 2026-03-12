"""Snapshot serving endpoint."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots").resolve()


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    # Sanitize: extract only the final path component, stripping any
    # directory separators or traversal sequences before touching the fs.
    safe_name = PurePosixPath(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = SNAPSHOTS_DIR / safe_name

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path=filepath, media_type="image/jpeg")
