"""Chromecast discovery endpoint — scan the local network for Cast devices."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Query

from couch_hound.api.schemas import (
    ChromecastDeviceInfo,
    ChromecastDiscoverResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chromecast"])


def _discover_devices(timeout: float) -> tuple[list[ChromecastDeviceInfo], float]:
    """Blocking scan for Chromecast devices on the local network."""
    import pychromecast

    start = time.monotonic()
    chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)
    elapsed = round(time.monotonic() - start, 2)
    try:
        devices = [
            ChromecastDeviceInfo(
                friendly_name=cc.cast_info.friendly_name,
                model_name=cc.cast_info.model_name,
                uuid=str(cc.cast_info.uuid),
            )
            for cc in chromecasts
        ]
    finally:
        browser.stop_discovery()
    devices.sort(key=lambda d: d.friendly_name.lower())
    return devices, elapsed


@router.get("/chromecasts/discover")
async def discover_chromecasts(
    timeout: float = Query(default=5.0, ge=1.0, le=15.0),
) -> ChromecastDiscoverResponse:
    """Scan the local network for available Chromecast devices."""
    devices, elapsed = await asyncio.to_thread(_discover_devices, timeout)
    logger.info("Chromecast scan found %d device(s) in %.1fs", len(devices), elapsed)
    return ChromecastDiscoverResponse(devices=devices, scan_duration=elapsed)
