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
