"""Tests for the crop capture module."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from couch_hound.config import CropCaptureConfig
from couch_hound.crop_capture import CropCapture
from couch_hound.detector import Detection, SnakeTile


@pytest.fixture
def crop_config(tmp_path: Path) -> CropCaptureConfig:
    return CropCaptureConfig(
        enabled=True,
        save_dir=str(tmp_path / "crops"),
        max_crops=5000,
        min_interval_secs=0.5,
        capture_negatives=False,
    )


@pytest.fixture
def capture(crop_config: CropCaptureConfig) -> CropCapture:
    return CropCapture(crop_config)


@pytest.fixture
def dummy_tile() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


class TestShouldCapture:
    def test_allows_first_capture(self, capture: CropCapture) -> None:
        assert capture.should_capture() is True

    def test_blocks_within_interval(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        capture.save_tile(dummy_tile, "dog", True, 0.9)
        assert capture.should_capture() is False

    def test_allows_after_interval(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        capture.save_tile(dummy_tile, "dog", True, 0.9)
        # Override last capture time to simulate elapsed time
        capture._last_capture_time = time.monotonic() - 1.0
        assert capture.should_capture() is True


class TestSaveTile:
    def test_saves_jpeg(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        path = capture.save_tile(dummy_tile, "dog", True, 0.85)
        assert path.exists()
        assert path.suffix == ".jpg"
        assert "pos_dog_0.85" in path.name

    def test_saves_negative(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        path = capture.save_tile(dummy_tile, "background", False, None)
        assert path.exists()
        assert "neg_background_none" in path.name

    def test_sanitizes_label_with_slash(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        """The default coco labels file contains "n/a" — the slash must not
        produce a nested (nonexistent) directory and crash the pipeline."""
        path = capture.save_tile(dummy_tile, "n/a", True, 0.9)
        assert path.exists()
        assert path.parent == Path(capture.config.save_dir)
        assert "n_a" in path.name

    def test_sanitizes_traversal_label(self, capture: CropCapture, dummy_tile: np.ndarray) -> None:
        path = capture.save_tile(dummy_tile, "../../evil", True, 0.9)
        assert path.exists()
        assert path.parent == Path(capture.config.save_dir)

    def test_prunes_over_limit(self, crop_config: CropCaptureConfig, tmp_path: Path) -> None:
        prune_config = CropCaptureConfig(
            enabled=True,
            save_dir=str(tmp_path / "prune_crops"),
            max_crops=100,
            min_interval_secs=0.5,
            capture_negatives=False,
        )
        cap = CropCapture(prune_config)
        save_dir = Path(prune_config.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Pre-populate directory with 99 dummy crops
        for i in range(99):
            (save_dir / f"crop_pos_dog_0.90_{i:06d}.jpg").write_bytes(b"fake")

        tile = np.zeros((50, 50, 3), dtype=np.uint8)
        # Save 3 more — should trigger pruning to max 100
        for _ in range(3):
            cap.save_tile(tile, "dog", True, 0.9)

        remaining = list(save_dir.glob("crop_*.jpg"))
        assert len(remaining) == 100

    def test_creates_directory(self, crop_config: CropCaptureConfig) -> None:
        cap = CropCapture(crop_config)
        tile = np.zeros((50, 50, 3), dtype=np.uint8)
        save_dir = Path(crop_config.save_dir)
        assert not save_dir.exists()
        cap.save_tile(tile, "dog", True, 0.9)
        assert save_dir.exists()


class TestSnakeTileIntegration:
    """Test that snake_detect populates tiles when return_tiles=True."""

    def test_return_tiles_false_has_empty_tiles(self) -> None:
        """When return_tiles is False, debug_info.tiles should be empty."""
        from couch_hound.config import DetectionConfig
        from couch_hound.detector import Detector

        det = Detector(DetectionConfig())
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        anchor_bbox = [0.1, 0.1, 0.9, 0.9]

        with patch.object(det, "detect_with_threshold", return_value=[]):
            with patch.object(
                det,
                "find_contour_regions",
                return_value=([(10, 10, 100, 100)], [np.array([[10, 10], [100, 10], [100, 100]])]),
            ):
                det._interpreter = MagicMock()  # bypass load check
                detections, debug_info = det.snake_detect(frame, anchor_bbox, return_tiles=False)
                assert debug_info is not None
                assert debug_info.tiles == []

    def test_return_tiles_true_populates_tiles(self) -> None:
        """When return_tiles is True, debug_info.tiles should contain SnakeTile objects."""
        from couch_hound.config import DetectionConfig
        from couch_hound.detector import Detector

        det = Detector(DetectionConfig())
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        anchor_bbox = [0.1, 0.1, 0.9, 0.9]

        mock_detection = Detection(label="dog", confidence=0.8, bbox=[0.2, 0.2, 0.8, 0.8])

        with patch.object(det, "detect_with_threshold", return_value=[mock_detection]):
            with patch.object(
                det,
                "find_contour_regions",
                return_value=([(10, 10, 100, 100)], [np.array([[10, 10], [100, 10], [100, 100]])]),
            ):
                det._interpreter = MagicMock()  # bypass load check
                detections, debug_info = det.snake_detect(frame, anchor_bbox, return_tiles=True)
                assert debug_info is not None
                assert len(debug_info.tiles) == 1
                tile = debug_info.tiles[0]
                assert isinstance(tile, SnakeTile)
                assert tile.image.shape[0] == 100
                assert tile.image.shape[1] == 100
                assert len(tile.detections) == 1
                assert tile.detections[0].label == "dog"
