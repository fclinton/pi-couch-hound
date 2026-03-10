"""System status and utility endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])

_start_time = time.time()


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Return system status."""
    return {
        "status": "running",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "version": "0.1.0",
    }


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for CI/CD and monitoring."""
    return {"status": "ok"}
