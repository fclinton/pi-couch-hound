"""Application log viewing endpoint."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Query, Request

from couch_hound.api.schemas import LogEntry, LogsResponse

router = APIRouter(tags=["logs"])

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(DEBUG|INFO|WARNING|ERROR)\s+\[(.+?)]\s+(.*)"
)

_MAX_LINES = 1000


def _read_and_parse(log_path: Path, max_lines: int, level: str | None) -> LogsResponse:
    """Read tail of the log file and parse into structured entries."""
    if not log_path.is_file():
        return LogsResponse(entries=[], total_lines=0, returned=0)

    with open(log_path) as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)

    # Parse all lines, then take the last N matching entries
    entries: list[LogEntry] = []
    for raw in all_lines:
        raw = raw.rstrip("\n")
        m = _LOG_LINE_RE.match(raw)
        if m:
            entries.append(
                LogEntry(
                    timestamp=m.group(1),
                    level=m.group(2),
                    logger=m.group(3),
                    message=m.group(4),
                )
            )
        elif entries:
            # Continuation line (e.g. traceback) — append to previous entry
            entries[-1].message += "\n" + raw

    if level:
        entries = [e for e in entries if e.level == level.upper()]

    tail = entries[-max_lines:]
    return LogsResponse(entries=tail, total_lines=total_lines, returned=len(tail))


@router.get("/logs")
async def get_logs(
    request: Request,
    lines: int = Query(default=100, ge=1, le=_MAX_LINES),
    level: str | None = Query(default=None),
) -> LogsResponse:
    """Return recent application log entries."""
    log_path = Path(request.app.state.config.logging.file)
    return await asyncio.to_thread(_read_and_parse, log_path, lines, level)
