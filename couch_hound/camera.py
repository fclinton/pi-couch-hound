"""Frame capture abstraction wrapping OpenCV VideoCapture."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy.typing as npt

from couch_hound.config import CameraConfig

logger = logging.getLogger(__name__)


class Camera:
    """Capture frames from a camera device or RTSP stream."""

    _MAX_CONSECUTIVE_FAILURES = 50

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._cap: cv2.VideoCapture | None = None
        self._consecutive_failures: int = 0

    def open(self) -> None:
        """Open the camera capture device."""
        source = self._config.source
        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera source: {source}")

        width, height = self._config.resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
        logger.info("Opened camera source=%s resolution=%dx%d", source, width, height)

    def close(self) -> None:
        """Release the camera capture device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def grab_frame(self) -> npt.NDArray[Any] | None:
        """Capture a single frame, returning None on failure.

        Raises RuntimeError after ``_MAX_CONSECUTIVE_FAILURES`` consecutive
        failures so the pipeline can attempt camera re-initialisation.
        """
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                raise RuntimeError(
                    f"Camera returned {self._consecutive_failures} consecutive empty frames"
                )
            return None
        self._consecutive_failures = 0
        return frame
