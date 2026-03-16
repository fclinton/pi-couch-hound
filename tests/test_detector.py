"""Tests for the LiteRT detector (mocked inference)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from couch_hound.config import DetectionConfig


@pytest.fixture(autouse=True)
def _mock_tflite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake ai_edge_litert module so detector.py can import it."""
    litert_mod = ModuleType("ai_edge_litert")
    interp_mod = ModuleType("ai_edge_litert.interpreter")
    interp_mod.Interpreter = MagicMock  # type: ignore[attr-defined]
    interp_mod.load_delegate = MagicMock  # type: ignore[attr-defined]
    litert_mod.interpreter = interp_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ai_edge_litert", litert_mod)
    monkeypatch.setitem(sys.modules, "ai_edge_litert.interpreter", interp_mod)

    import couch_hound.detector as det_module

    monkeypatch.setattr(det_module, "_HAS_TFLITE", True)


def _make_interpreter_mock(
    labels: list[str],
    detections: list[tuple[str, float, list[float]]],
) -> MagicMock:
    """Build a mock LiteRT interpreter with canned outputs."""
    interp = MagicMock()
    interp.get_input_details.return_value = [
        {"shape": [1, 300, 300, 3], "dtype": np.uint8, "index": 0}
    ]
    interp.get_output_details.return_value = [
        {"index": 0},
        {"index": 1},
        {"index": 2},
        {"index": 3},
    ]

    label_to_id = {lbl: i for i, lbl in enumerate(labels)}
    boxes = []
    classes = []
    scores = []
    for label, conf, bbox in detections:
        x1, y1, x2, y2 = bbox
        boxes.append([y1, x1, y2, x2])
        classes.append(float(label_to_id.get(label, 0)))
        scores.append(conf)

    count = len(detections)

    def get_tensor(idx: int) -> Any:
        tensors = {
            0: np.array([boxes], dtype=np.float32),
            1: np.array([classes], dtype=np.float32),
            2: np.array([scores], dtype=np.float32),
            3: np.array([count], dtype=np.float32),
        }
        return tensors[idx]

    interp.get_tensor.side_effect = get_tensor
    return interp


class TestDetector:
    def test_load_model(self, tmp_path: Path) -> None:
        from couch_hound.detector import Detector

        model_file = tmp_path / "test.tflite"
        model_file.write_bytes(b"fake model")
        labels_file = tmp_path / "labels.txt"
        labels_file.write_text("dog\ncat\nperson\n")

        config = DetectionConfig(
            model=str(model_file),
            labels=str(labels_file),
        )
        detector = Detector(config)

        mock_interp = MagicMock()
        mock_interp.get_input_details.return_value = [
            {"shape": [1, 300, 300, 3], "dtype": np.uint8, "index": 0}
        ]
        mock_interp.get_output_details.return_value = [{"index": i} for i in range(4)]

        import couch_hound.detector as det_module

        original_interpreter = getattr(det_module, "Interpreter", None)
        det_module.Interpreter = MagicMock(return_value=mock_interp)  # type: ignore[attr-defined]
        try:
            detector.load()
            mock_interp.allocate_tensors.assert_called_once()
            assert len(detector._labels) == 3
        finally:
            if original_interpreter is not None:
                det_module.Interpreter = original_interpreter  # type: ignore[attr-defined]

    def test_detect_returns_all_detections_above_threshold(self) -> None:
        from couch_hound.detector import Detector

        labels = ["dog", "cat", "person"]
        interp = _make_interpreter_mock(
            labels,
            [
                ("dog", 0.92, [0.1, 0.2, 0.5, 0.6]),
                ("cat", 0.85, [0.3, 0.4, 0.7, 0.8]),
                ("dog", 0.40, [0.0, 0.0, 0.1, 0.1]),
            ],
        )
        config = DetectionConfig(confidence_threshold=0.60, target_label="dog")
        detector = Detector(config)
        detector._interpreter = interp
        detector._input_details = interp.get_input_details()
        detector._output_details = interp.get_output_details()
        detector._labels = labels

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)

        # Returns both dog and cat (above threshold), but not the low-confidence dog
        assert len(results) == 2
        assert results[0].label == "dog"
        assert results[0].confidence == pytest.approx(0.92)
        assert results[0].is_target is True
        assert results[1].label == "cat"
        assert results[1].confidence == pytest.approx(0.85)
        assert results[1].is_target is False

    def test_marks_non_target_detections(self) -> None:
        from couch_hound.detector import Detector

        labels = ["dog", "cat"]
        interp = _make_interpreter_mock(labels, [("cat", 0.95, [0.1, 0.2, 0.5, 0.6])])
        config = DetectionConfig(confidence_threshold=0.50, target_label="dog")
        detector = Detector(config)
        detector._interpreter = interp
        detector._input_details = interp.get_input_details()
        detector._output_details = interp.get_output_details()
        detector._labels = labels

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)

        assert len(results) == 1
        assert results[0].label == "cat"
        assert results[0].is_target is False

    def test_detect_without_load_raises(self) -> None:
        from couch_hound.detector import Detector

        detector = Detector(DetectionConfig())
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="not loaded"):
            detector.detect(frame)

    def test_unload_clears_interpreter(self) -> None:
        from couch_hound.detector import Detector

        detector = Detector(DetectionConfig())
        detector._interpreter = MagicMock()
        detector.unload()
        assert detector._interpreter is None

    def test_detect_with_threshold_overrides_config(self) -> None:
        from couch_hound.detector import Detector

        labels = ["dog", "cat"]
        interp = _make_interpreter_mock(
            labels,
            [("dog", 0.45, [0.1, 0.2, 0.5, 0.6])],
        )
        config = DetectionConfig(confidence_threshold=0.60, target_label="dog")
        detector = Detector(config)
        detector._interpreter = interp
        detector._input_details = interp.get_input_details()
        detector._output_details = interp.get_output_details()
        detector._labels = labels

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Normal threshold (0.60) filters it out
        assert len(detector.detect(frame)) == 0
        # Lower threshold picks it up
        results = detector.detect_with_threshold(frame, 0.40)
        assert len(results) == 1
        assert results[0].label == "dog"
        # Original threshold is restored
        assert config.confidence_threshold == pytest.approx(0.60)

    def test_find_contour_regions_finds_blobs(self) -> None:
        from couch_hound.detector import Detector

        # Create a crop with a white rectangle (object) on black background
        crop = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(crop, (100, 80), (200, 180), (255, 255, 255), -1)

        regions, contours = Detector.find_contour_regions(
            crop, min_contour_area=500, contour_padding=0.1
        )
        assert len(regions) >= 1
        assert len(contours) >= 1
        # The region should roughly cover the white rectangle
        x, y, w, h = regions[0]
        assert x <= 100 and y <= 80
        assert x + w >= 200 and y + h >= 180

    def test_find_contour_regions_ignores_small_blobs(self) -> None:
        from couch_hound.detector import Detector

        # Tiny 5x5 white square — below min_contour_area
        crop = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(crop, (100, 100), (105, 105), (255, 255, 255), -1)

        regions, contours = Detector.find_contour_regions(
            crop, min_contour_area=800, contour_padding=0.1
        )
        assert len(regions) == 0
        assert len(contours) == 0

    def test_find_contour_regions_merges_overlapping(self) -> None:
        from couch_hound.detector import Detector

        # Two overlapping rectangles should merge into one region
        crop = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(crop, (50, 50), (180, 150), (255, 255, 255), -1)
        cv2.rectangle(crop, (150, 50), (280, 150), (255, 255, 255), -1)

        regions, _contours = Detector.find_contour_regions(
            crop, min_contour_area=500, contour_padding=0.1
        )
        # Should merge into a single region
        assert len(regions) == 1

    def test_snake_detect_remaps_to_full_frame(self) -> None:
        from couch_hound.detector import Detector

        labels = ["dog"]
        interp = _make_interpreter_mock(
            labels,
            [("dog", 0.85, [0.1, 0.1, 0.9, 0.9])],
        )
        config = DetectionConfig(confidence_threshold=0.40, target_label="dog")
        detector = Detector(config)
        detector._interpreter = interp
        detector._input_details = interp.get_input_details()
        detector._output_details = interp.get_output_details()
        detector._labels = labels

        # Create frame with a visible blob inside the anchor region
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Place a white blob inside anchor area (right half)
        cv2.rectangle(frame, (700, 200), (900, 400), (255, 255, 255), -1)

        anchor_bbox = [0.5, 0.0, 1.0, 1.0]  # right half
        results, debug_info = detector.snake_detect(frame, anchor_bbox, anchor_padding=0.0)
        assert len(results) >= 1
        # All bboxes should be in full-frame normalised coords (0..1)
        for det in results:
            assert all(0.0 <= v <= 1.0 for v in det.bbox)
        # Debug info should be populated
        assert debug_info is not None
        assert len(debug_info.tile_bboxes) >= 1
        assert len(debug_info.contour_points) >= 1

    def test_snake_detect_tiny_anchor_returns_empty(self) -> None:
        from couch_hound.detector import Detector

        config = DetectionConfig(confidence_threshold=0.50, target_label="dog")
        detector = Detector(config)
        detector._interpreter = MagicMock()

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        anchor_bbox = [0.0, 0.0, 0.005, 0.005]
        results, debug_info = detector.snake_detect(frame, anchor_bbox)
        assert results == []
        assert debug_info is None

    def test_snake_detect_no_contours_falls_back_to_full_crop(self) -> None:
        from couch_hound.detector import Detector

        labels = ["dog"]
        interp = _make_interpreter_mock(
            labels,
            [("dog", 0.70, [0.3, 0.3, 0.7, 0.7])],
        )
        config = DetectionConfig(confidence_threshold=0.40, target_label="dog")
        detector = Detector(config)
        detector._interpreter = interp
        detector._input_details = interp.get_input_details()
        detector._output_details = interp.get_output_details()
        detector._labels = labels

        # Uniform grey frame — no edges, no contours
        frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
        anchor_bbox = [0.2, 0.2, 0.8, 0.8]

        results, debug_info = detector.snake_detect(frame, anchor_bbox, anchor_padding=0.0)
        # Falls back to running on whole anchor crop
        assert len(results) >= 1
        assert debug_info is not None
        # Fallback: no contour points but still has tile bboxes
        assert len(debug_info.contour_points) == 0
        assert len(debug_info.tile_bboxes) >= 1


class TestNms:
    def test_nms_keeps_highest_confidence(self) -> None:
        from couch_hound.detector import Detection, _nms

        dets = [
            Detection(label="dog", confidence=0.90, bbox=[0.1, 0.1, 0.5, 0.5]),
            Detection(label="dog", confidence=0.70, bbox=[0.12, 0.12, 0.52, 0.52]),
        ]
        result = _nms(dets, iou_threshold=0.3)
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.90)

    def test_nms_keeps_non_overlapping(self) -> None:
        from couch_hound.detector import Detection, _nms

        dets = [
            Detection(label="dog", confidence=0.90, bbox=[0.0, 0.0, 0.2, 0.2]),
            Detection(label="cat", confidence=0.80, bbox=[0.8, 0.8, 1.0, 1.0]),
        ]
        result = _nms(dets, iou_threshold=0.3)
        assert len(result) == 2

    def test_nms_empty_list(self) -> None:
        from couch_hound.detector import _nms

        assert _nms([], iou_threshold=0.5) == []


class TestMergeOverlappingRects:
    def test_merges_overlapping(self) -> None:
        from couch_hound.detector import _merge_overlapping_rects

        rects = [(10, 10, 100, 100), (80, 10, 100, 100)]
        merged = _merge_overlapping_rects(rects)
        assert len(merged) == 1
        x, y, w, h = merged[0]
        assert x == 10 and y == 10
        assert x + w == 180 and y + h == 110

    def test_keeps_non_overlapping(self) -> None:
        from couch_hound.detector import _merge_overlapping_rects

        rects = [(0, 0, 50, 50), (200, 200, 50, 50)]
        merged = _merge_overlapping_rects(rects)
        assert len(merged) == 2
