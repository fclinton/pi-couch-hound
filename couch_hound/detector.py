"""TFLite inference wrapper for object detection."""

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
    from tflite_runtime.interpreter import Interpreter  # noqa: I001
    from tflite_runtime.interpreter import load_delegate

    _HAS_TFLITE = True
except ImportError:
    _HAS_TFLITE = False


@dataclass
class Detection:
    """A single object detection result."""

    label: str
    confidence: float
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2] normalized


class Detector:
    """TFLite object-detection model wrapper."""

    def __init__(self, config: DetectionConfig) -> None:
        self._config = config
        self._interpreter: Any = None
        self._labels: list[str] = []
        self._input_details: list[dict[str, Any]] = []
        self._output_details: list[dict[str, Any]] = []

    def load(self) -> None:
        """Load the TFLite model and labels file."""
        if not _HAS_TFLITE:
            raise RuntimeError(
                "tflite_runtime is not installed. Install with: pip install tflite-runtime"
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
            if label != self._config.target_label:
                continue

            # boxes are [y1, x1, y2, x2] normalized — convert to [x1, y1, x2, y2]
            y1, x1, y2, x2 = (float(v) for v in boxes[i])
            detections.append(Detection(label=label, confidence=confidence, bbox=[x1, y1, x2, y2]))

        return detections
