"""Snapshot serving endpoint."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["snapshots"])

SNAPSHOTS_DIR = Path("snapshots").resolve()

# Only allow simple filenames: alphanumerics, hyphens, underscores, dots.
# No path separators, no ".." sequences, no hidden files starting with ".".
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _sanitize_path(filename: str, base_dir: Path) -> str:
    """Sanitize a user-supplied filename and return a safe absolute path.

    Validates the filename against an allowlist regex, then normalizes and
    resolves the full path to ensure it stays within *base_dir*.

    Raises HTTPException(400) if the filename is invalid or escapes the base.
    """
    if not _SAFE_FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Source - https://stackoverflow.com/a/78879674
    # Posted by andycaine
    # Retrieved 2026-03-12, License - CC BY-SA 4.0
    fullpath = os.path.normpath(os.path.realpath(os.path.join(base_dir, filename)))
    if not fullpath.startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    return fullpath


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    """Serve a snapshot image by filename."""
    safe_path = _sanitize_path(filename, SNAPSHOTS_DIR)

    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path=safe_path, media_type="image/jpeg")
