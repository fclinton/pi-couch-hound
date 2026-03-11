"""Tests for the TFLite detector (mocked inference)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from couch_hound.config import DetectionConfig


@pytest.fixture(autouse=True)
def _mock_tflite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake tflite_runtime module so detector.py can import it."""
    tflite_mod = ModuleType("tflite_runtime")
    interp_mod = ModuleType("tflite_runtime.interpreter")
    interp_mod.Interpreter = MagicMock  # type: ignore[attr-defined]
    interp_mod.load_delegate = MagicMock  # type: ignore[attr-defined]
    tflite_mod.interpreter = interp_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tflite_runtime", tflite_mod)
    monkeypatch.setitem(sys.modules, "tflite_runtime.interpreter", interp_mod)

    import couch_hound.detector as det_module

    monkeypatch.setattr(det_module, "_HAS_TFLITE", True)


def _make_interpreter_mock(
    labels: list[str],
    detections: list[tuple[str, float, list[float]]],
) -> MagicMock:
    """Build a mock TFLite interpreter with canned outputs."""
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

    def test_detect_returns_filtered_detections(self) -> None:
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

        assert len(results) == 1
        assert results[0].label == "dog"
        assert results[0].confidence == pytest.approx(0.92)

    def test_filters_by_target_label(self) -> None:
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

        assert len(results) == 0

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
