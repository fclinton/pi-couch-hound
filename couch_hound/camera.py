"""Frame capture abstraction wrapping OpenCV VideoCapture."""

from __future__ import annotations

import logging
import threading
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
        # cv2.VideoCapture is not thread-safe. The detection and stream loops
        # both call grab_frame via asyncio.to_thread, and close() can race a
        # concurrent read — serialize all capture access to avoid native crashes.
        self._lock = threading.Lock()

    def open(self) -> None:
        """Open the camera capture device."""
        source = self._config.source
        with self._lock:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                cap.release()
                raise RuntimeError(f"Failed to open camera source: {source}")

            width, height = self._config.resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
            self._cap = cap
            self._consecutive_failures = 0
        logger.info("Opened camera source=%s resolution=%dx%d", source, width, height)

    def close(self) -> None:
        """Release the camera capture device."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def grab_frame(self) -> npt.NDArray[Any] | None:
        """Capture a single frame, returning None on failure.

        Raises RuntimeError after ``_MAX_CONSECUTIVE_FAILURES`` consecutive
        failures so the pipeline can attempt camera re-initialisation.
        """
        with self._lock:
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
