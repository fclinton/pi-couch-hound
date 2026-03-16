"""LiteRT (ai-edge-litert) inference wrapper for object detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from couch_hound.config import DetectionConfig

logger = logging.getLogger(__name__)

try:
    from ai_edge_litert.interpreter import Interpreter  # noqa: I001
    from ai_edge_litert.interpreter import load_delegate

    _HAS_TFLITE = True
except ImportError:
    _HAS_TFLITE = False


@dataclass
class Detection:
    """A single object detection result."""

    label: str
    confidence: float
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2] normalized
    is_target: bool = False


class Detector:
    """LiteRT object-detection model wrapper."""

    def __init__(self, config: DetectionConfig) -> None:
        self._config = config
        self._interpreter: Any = None
        self._labels: list[str] = []
        self._input_details: list[dict[str, Any]] = []
        self._output_details: list[dict[str, Any]] = []

    def load(self) -> None:
        """Load the LiteRT model and labels file."""
        if not _HAS_TFLITE:
            raise RuntimeError(
                "ai-edge-litert is not installed. Install with: pip install ai-edge-litert"
            )

        model_path = Path(self._config.model)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        delegates = None
        if self._config.use_coral:
            try:
                delegates = [load_delegate("libedgetpu.so.1")]
            except (ValueError, OSError) as exc:
                logger.warning("Failed to load Edge TPU delegate: %s", exc)
                delegates = None

        self._interpreter = Interpreter(
            model_path=str(model_path),
            experimental_delegates=delegates,
        )
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

        self._labels = self._load_labels(Path(self._config.labels))
        logger.info("Loaded model %s with %d labels", model_path, len(self._labels))

    def _load_labels(self, labels_path: Path) -> list[str]:
        """Read labels file, one label per line."""
        if not labels_path.exists():
            logger.warning("Labels file not found: %s", labels_path)
            return []
        return [line.strip() for line in labels_path.read_text().splitlines() if line.strip()]

    def unload(self) -> None:
        """Release the interpreter."""
        self._interpreter = None

    def detect(self, frame: npt.NDArray[Any]) -> list[Detection]:
        """Run inference on a frame and return filtered detections."""
        if self._interpreter is None:
            raise RuntimeError("Detector not loaded — call load() first")

        input_shape = self._input_details[0]["shape"]
        height, width = int(input_shape[1]), int(input_shape[2])

        resized = cv2.resize(frame, (width, height))
        input_data = np.expand_dims(resized, axis=0)

        # Handle float vs uint8 models
        if self._input_details[0]["dtype"] == np.float32:
            input_data = (input_data.astype(np.float32) - 127.5) / 127.5

        self._interpreter.set_tensor(self._input_details[0]["index"], input_data)
        self._interpreter.invoke()

        # Standard SSD output format: boxes, classes, scores, count
        boxes = self._interpreter.get_tensor(self._output_details[0]["index"])[0]
        classes = self._interpreter.get_tensor(self._output_details[1]["index"])[0]
        scores = self._interpreter.get_tensor(self._output_details[2]["index"])[0]
        count = int(self._interpreter.get_tensor(self._output_details[3]["index"])[0])

        detections: list[Detection] = []
        for i in range(count):
            confidence = float(scores[i])
            if confidence < self._config.confidence_threshold:
                continue

            class_id = int(classes[i])
            label = self._labels[class_id] if class_id < len(self._labels) else str(class_id)

            # boxes are [y1, x1, y2, x2] normalized — convert to [x1, y1, x2, y2]
            y1, x1, y2, x2 = (float(v) for v in boxes[i])
            detections.append(
                Detection(
                    label=label,
                    confidence=confidence,
                    bbox=[x1, y1, x2, y2],
                    is_target=(label == self._config.target_label),
                )
            )

        return detections

    def detect_with_threshold(
        self, frame: npt.NDArray[Any], confidence_threshold: float
    ) -> list[Detection]:
        """Run inference with an overridden confidence threshold."""
        original = self._config.confidence_threshold
        self._config.confidence_threshold = confidence_threshold
        try:
            return self.detect(frame)
        finally:
            self._config.confidence_threshold = original

    def detect_region(
        self,
        frame: npt.NDArray[Any],
        region: list[float],
        confidence_threshold: float | None = None,
        padding: float = 0.0,
    ) -> list[Detection]:
        """Crop a region from the frame, run detection, and remap bboxes.

        Args:
            frame: Full-resolution frame (H, W, 3).
            region: Normalized [x1, y1, x2, y2] bounding box to crop.
            confidence_threshold: Override threshold for this detection pass.
            padding: Fraction of region size to add as padding on each side.

        Returns:
            Detections with bboxes mapped back to full-frame normalized coords.
        """
        h, w = frame.shape[:2]
        rx1, ry1, rx2, ry2 = region

        # Add padding around the anchor region
        rw, rh = rx2 - rx1, ry2 - ry1
        px1 = max(0.0, rx1 - rw * padding)
        py1 = max(0.0, ry1 - rh * padding)
        px2 = min(1.0, rx2 + rw * padding)
        py2 = min(1.0, ry2 + rh * padding)

        # Convert to pixel coordinates and crop
        cx1, cy1 = int(px1 * w), int(py1 * h)
        cx2, cy2 = int(px2 * w), int(py2 * h)

        # Ensure minimum crop size
        if cx2 - cx1 < 10 or cy2 - cy1 < 10:
            return []

        cropped = frame[cy1:cy2, cx1:cx2]

        threshold = confidence_threshold or self._config.confidence_threshold
        detections = self.detect_with_threshold(cropped, threshold)

        # Remap bboxes from crop-local normalized coords to full-frame normalized
        crop_w = px2 - px1
        crop_h = py2 - py1
        for det in detections:
            det.bbox = [
                px1 + det.bbox[0] * crop_w,  # x1
                py1 + det.bbox[1] * crop_h,  # y1
                px1 + det.bbox[2] * crop_w,  # x2
                py1 + det.bbox[3] * crop_h,  # y2
            ]

        return detections
