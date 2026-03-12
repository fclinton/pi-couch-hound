"""Snapshot serving endpoint."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots").resolve()

# Only allow simple filenames: alphanumerics, hyphens, underscores, dots.
# No path separators, no ".." sequences, no hidden files starting with ".".
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    if not _SAFE_FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = SNAPSHOTS_DIR / filename

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path=filepath, media_type="image/jpeg")
