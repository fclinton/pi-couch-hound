"""ROI (Region of Interest) endpoints — get, save, and clear the detection zone."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from couch_hound.api.schemas import RoiResponse, RoiUpdateRequest
from couch_hound.config import AppConfig, save_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["roi"])


@router.get("/roi")
async def get_roi(request: Request) -> RoiResponse:
    """Get the current ROI polygon and settings."""
    config: AppConfig = request.app.state.config
    roi = config.detection.roi
    return RoiResponse(
        enabled=roi.enabled,
        polygon=roi.polygon,
        min_overlap=roi.min_overlap,
    )


@router.put("/roi")
async def update_roi(body: RoiUpdateRequest, request: Request) -> RoiResponse:
    """Save a new ROI polygon (from the canvas editor).

    Automatically enables ROI filtering when a polygon is saved.
    """
    if len(body.polygon) < 3:
        raise HTTPException(
            status_code=422,
            detail="ROI polygon must have at least 3 points.",
        )

    for i, point in enumerate(body.polygon):
        if len(point) != 2:
            raise HTTPException(
                status_code=422,
                detail=f"Point {i} must have exactly 2 coordinates [x, y].",
            )
        if not (0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0):
            raise HTTPException(
                status_code=422,
                detail=f"Point {i} coordinates must be in [0.0, 1.0] range.",
            )

    config: AppConfig = request.app.state.config
    config.detection.roi.enabled = True
    config.detection.roi.polygon = body.polygon
    if body.min_overlap is not None:
        config.detection.roi.min_overlap = body.min_overlap

    save_config(config, request.app.state.config_path)
    logger.info("ROI polygon updated (%d points)", len(body.polygon))

    roi = config.detection.roi
    return RoiResponse(
        enabled=roi.enabled,
        polygon=roi.polygon,
        min_overlap=roi.min_overlap,
    )


@router.delete("/roi", status_code=200)
async def clear_roi(request: Request) -> RoiResponse:
    """Clear the ROI — disables zone filtering."""
    config: AppConfig = request.app.state.config
    config.detection.roi.enabled = False
    config.detection.roi.polygon = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]]
    config.detection.roi.min_overlap = 0.3

    save_config(config, request.app.state.config_path)
    logger.info("ROI cleared and disabled")

    roi = config.detection.roi
    return RoiResponse(
        enabled=roi.enabled,
        polygon=roi.polygon,
        min_overlap=roi.min_overlap,
    )
