"""System status and utility endpoints."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Request

from couch_hound.actions import create_action
from couch_hound.api.schemas import (
    ActionResultItem,
    RestartResponse,
    StatusResponse,
    TestAllActionsResponse,
)
from couch_hound.api.websocket import get_system_metrics
from couch_hound.config import AppConfig
from couch_hound.pipeline import DetectionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

_start_time = time.time()


@router.get("/status")
async def get_status(request: Request) -> StatusResponse:
    """Return system status including detection stats and hardware metrics."""
    pipeline: DetectionPipeline = request.app.state.pipeline
    metrics = await asyncio.to_thread(get_system_metrics)

    return StatusResponse(
        status="running",
        uptime_seconds=round(time.time() - _start_time, 1),
        version="0.1.0",
        detection_count=pipeline.stats.detection_count,
        last_detection_time=pipeline.stats.last_detection_time,
        cpu_percent=metrics["cpu_percent"],
        memory_percent=metrics["memory_percent"],
        temperature=metrics["temperature"],
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for CI/CD and monitoring."""
    return {"status": "ok"}


@router.post("/test-actions")
async def test_all_actions(request: Request) -> TestAllActionsResponse:
    """Fire all enabled actions once for testing without a real detection."""
    config: AppConfig = request.app.state.config
    results: list[ActionResultItem] = []
    for action_cfg in config.actions:
        if not action_cfg.enabled:
            continue
        try:
            action = create_action(action_cfg)
            await action.execute({})
            results.append(
                ActionResultItem(
                    name=action_cfg.name, success=True, message="Action executed successfully"
                )
            )
        except Exception as exc:
            results.append(ActionResultItem(name=action_cfg.name, success=False, message=str(exc)))
            logger.warning("Test-fire of action '%s' failed: %s", action_cfg.name, exc)
    succeeded = sum(1 for r in results if r.success)
    return TestAllActionsResponse(
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )


@router.post("/restart")
async def restart_pipeline(request: Request) -> RestartResponse:
    """Restart the detection pipeline without restarting the process."""
    pipeline: DetectionPipeline = request.app.state.pipeline
    await pipeline.restart()
    return RestartResponse(status="ok", message="Pipeline restarted successfully")
