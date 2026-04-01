"""Crop capture — saves 2-stage detection tile crops for model training."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy.typing as npt

from couch_hound.config import CropCaptureConfig

logger = logging.getLogger(__name__)


class CropCapture:
    """Rate-limited saver for detection tile crops with auto-pruning."""

    def __init__(self, config: CropCaptureConfig) -> None:
        self._config = config
        self._save_dir = Path(config.save_dir)
        self._last_capture_time: float = 0.0

    @property
    def config(self) -> CropCaptureConfig:
        """Current crop capture configuration."""
        return self._config

    def should_capture(self) -> bool:
        """Check whether enough time has elapsed since the last capture."""
        now = time.monotonic()
        return now - self._last_capture_time >= self._config.min_interval_secs

    def save_tile(
        self,
        tile: npt.NDArray[Any],
        label: str,
        is_positive: bool,
        confidence: float | None,
    ) -> Path:
        """Save a tile crop as JPEG and prune oldest if over limit.

        This method is synchronous — call via ``asyncio.to_thread()``.
        """
        self._save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
        prefix = "pos" if is_positive else "neg"
        conf_str = f"{confidence:.2f}" if confidence is not None else "none"
        filename = f"crop_{prefix}_{label}_{conf_str}_{timestamp}.jpg"
        filepath = self._save_dir / filename

        success, buf = cv2.imencode(".jpg", tile)
        if not success:
            raise RuntimeError("Failed to encode tile crop as JPEG")
        filepath.write_bytes(buf.tobytes())

        self._last_capture_time = time.monotonic()

        # Prune oldest crops if over limit
        max_crops = self._config.max_crops
        if max_crops > 0:
            existing = sorted(self._save_dir.glob("crop_*.jpg"))
            while len(existing) > max_crops:
                existing.pop(0).unlink()

        logger.debug("Saved crop %s (%s, conf=%s)", filepath.name, label, conf_str)
        return filepath
