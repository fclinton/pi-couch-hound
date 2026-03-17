"""Tests for the camera frame grabber (mocked OpenCV)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from couch_hound.camera import Camera
from couch_hound.config import CameraConfig


class TestCamera:
    def test_open_and_close(self) -> None:
        config = CameraConfig(source=0, resolution=[640, 480])
        camera = Camera(config)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        with patch("couch_hound.camera.cv2.VideoCapture", return_value=mock_cap):
            camera.open()
            assert camera._cap is not None
            mock_cap.set.assert_any_call(3, 640.0)  # CAP_PROP_FRAME_WIDTH = 3
            mock_cap.set.assert_any_call(4, 480.0)  # CAP_PROP_FRAME_HEIGHT = 4

        camera.close()
        mock_cap.release.assert_called_once()
        assert camera._cap is None

    def test_open_failure_raises(self) -> None:
        config = CameraConfig(source=99)
        camera = Camera(config)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        with patch("couch_hound.camera.cv2.VideoCapture", return_value=mock_cap):
            with pytest.raises(RuntimeError, match="Failed to open"):
                camera.open()

    def test_grab_frame_success(self) -> None:
        config = CameraConfig()
        camera = Camera(config)
        frame_data = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, frame_data)
        camera._cap = mock_cap

        result = camera.grab_frame()
        assert result is not None
        assert result.shape == (480, 640, 3)

    def test_grab_frame_failure(self) -> None:
        config = CameraConfig()
        camera = Camera(config)

        mock_cap = MagicMock()
        mock_cap.read.return_value = (False, None)
        camera._cap = mock_cap

        assert camera.grab_frame() is None

    def test_grab_frame_without_open(self) -> None:
        config = CameraConfig()
        camera = Camera(config)
        assert camera.grab_frame() is None

    def test_consecutive_failures_raises(self) -> None:
        """Camera raises RuntimeError after too many consecutive failures."""
        config = CameraConfig()
        camera = Camera(config)

        mock_cap = MagicMock()
        mock_cap.read.return_value = (False, None)
        camera._cap = mock_cap

        # Should return None for failures below the threshold
        for _ in range(Camera._MAX_CONSECUTIVE_FAILURES - 1):
            assert camera.grab_frame() is None

        # The next failure should raise
        with pytest.raises(RuntimeError, match="consecutive empty frames"):
            camera.grab_frame()

    def test_consecutive_failures_resets_on_success(self) -> None:
        """Failure counter resets when a frame is successfully captured."""
        config = CameraConfig()
        camera = Camera(config)
        frame_data = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        camera._cap = mock_cap

        # Accumulate some failures
        mock_cap.read.return_value = (False, None)
        for _ in range(10):
            camera.grab_frame()
        assert camera._consecutive_failures == 10

        # One success should reset the counter
        mock_cap.read.return_value = (True, frame_data)
        camera.grab_frame()
        assert camera._consecutive_failures == 0
