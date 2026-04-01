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


@dataclass
class SnakeTile:
    """A single tile crop from snake detection, with its inference results."""

    image: npt.NDArray[Any]  # the raw tile crop (numpy array)
    detections: list[Detection]  # detections found in this tile (may be empty)
    tile_bbox: list[float]  # full-frame normalised [x1, y1, x2, y2]


@dataclass
class SnakeDebugInfo:
    """Debug visualisation data from a snake_detect pass."""

    anchor_bbox: list[float]  # [x1, y1, x2, y2] normalised, with padding applied
    tile_bboxes: list[list[float]]  # each [x1, y1, x2, y2] normalised
    contour_points: list[list[list[int]]]  # raw contour point arrays (pixel coords)
    crop_offset: tuple[int, int] = (0, 0)  # (x, y) pixel offset of anchor crop
    crop_size: tuple[int, int] = (0, 0)  # (w, h) pixel size of anchor crop
    tiles: list[SnakeTile] = field(default_factory=list)  # populated when return_tiles=True


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

    @staticmethod
    def find_contour_regions(
        crop: npt.NDArray[Any],
        min_contour_area: int = 800,
        contour_padding: float = 0.25,
    ) -> tuple[list[tuple[int, int, int, int]], list[npt.NDArray[Any]]]:
        """Use edge-based active contours (snakes) to find object regions.

        Applies Canny edge detection, dilates to close gaps, then finds
        contours. Each contour above ``min_contour_area`` pixels produces a
        padded bounding box in pixel coordinates.

        Returns:
            Tuple of (merged bounding rects, raw contour arrays that passed
            the area filter).  Rects are (x, y, w, h) in pixel coords.
        """
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        # Dilate to merge nearby edges into coherent blobs
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        ch, cw = crop.shape[:2]
        regions: list[tuple[int, int, int, int]] = []
        kept_contours: list[npt.NDArray[Any]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_contour_area:
                continue
            kept_contours.append(cnt)
            x, y, w, h = cv2.boundingRect(cnt)
            # Pad the bounding rect so the model sees surrounding context
            pad_x = int(w * contour_padding)
            pad_y = int(h * contour_padding)
            x = max(0, x - pad_x)
            y = max(0, y - pad_y)
            w = min(cw - x, w + 2 * pad_x)
            h = min(ch - y, h + 2 * pad_y)
            regions.append((x, y, w, h))

        return _merge_overlapping_rects(regions), kept_contours

    def snake_detect(
        self,
        frame: npt.NDArray[Any],
        anchor_bbox: list[float],
        anchor_padding: float = 0.10,
        confidence_threshold: float | None = None,
        min_contour_area: int = 800,
        contour_padding: float = 0.25,
        return_tiles: bool = False,
    ) -> tuple[list[Detection], SnakeDebugInfo | None]:
        """Detect objects by snaking contour regions within an anchor bbox.

        1. Crop the anchor region (+ padding) from the full-res frame.
        2. Run active-contour edge detection to find object outlines.
        3. For each contour, crop a tight box and run the model at full 300x300
           resolution — no wasted inference on empty cushions.
        4. Remap all detections back to full-frame normalised coordinates.
        5. Deduplicate with IoU-based non-max suppression.

        Returns:
            Tuple of (detections, debug_info).  ``debug_info`` is always
            populated so callers can decide whether to render it.
        """
        fh, fw = frame.shape[:2]
        ax1, ay1, ax2, ay2 = anchor_bbox

        # Pad the anchor region
        aw, ah = ax2 - ax1, ay2 - ay1
        px1 = max(0.0, ax1 - aw * anchor_padding)
        py1 = max(0.0, ay1 - ah * anchor_padding)
        px2 = min(1.0, ax2 + aw * anchor_padding)
        py2 = min(1.0, ay2 + ah * anchor_padding)

        # Pixel coords of anchor crop
        crop_x1, crop_y1 = int(px1 * fw), int(py1 * fh)
        crop_x2, crop_y2 = int(px2 * fw), int(py2 * fh)
        if crop_x2 - crop_x1 < 20 or crop_y2 - crop_y1 < 20:
            return [], None

        anchor_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

        # Find object contours within the anchor crop
        regions, raw_contours = self.find_contour_regions(
            anchor_crop, min_contour_area, contour_padding
        )
        fallback = False
        if not regions:
            # No contours — run one pass on the whole anchor crop as fallback
            regions = [(0, 0, anchor_crop.shape[1], anchor_crop.shape[0])]
            fallback = True

        threshold = confidence_threshold or self._config.confidence_threshold
        all_detections: list[Detection] = []
        tile_bboxes: list[list[float]] = []
        snake_tiles: list[SnakeTile] = []

        for rx, ry, rw, rh in regions:
            tile = anchor_crop[ry : ry + rh, rx : rx + rw]
            if tile.shape[0] < 10 or tile.shape[1] < 10:
                continue

            # Record tile bbox in full-frame normalised coords for debug
            tile_bbox = [
                (crop_x1 + rx) / fw,
                (crop_y1 + ry) / fh,
                (crop_x1 + rx + rw) / fw,
                (crop_y1 + ry + rh) / fh,
            ]
            tile_bboxes.append(tile_bbox)

            detections = self.detect_with_threshold(tile, threshold)

            # Remap: tile-local normalised → full-frame normalised
            for det in detections:
                # tile-local → anchor-crop pixel
                dx1 = rx + det.bbox[0] * rw
                dy1 = ry + det.bbox[1] * rh
                dx2 = rx + det.bbox[2] * rw
                dy2 = ry + det.bbox[3] * rh
                # anchor-crop pixel → full-frame normalised
                det.bbox = [
                    (crop_x1 + dx1) / fw,
                    (crop_y1 + dy1) / fh,
                    (crop_x1 + dx2) / fw,
                    (crop_y1 + dy2) / fh,
                ]
                all_detections.append(det)

            if return_tiles:
                snake_tiles.append(
                    SnakeTile(image=tile, detections=detections, tile_bbox=tile_bbox)
                )

        # Build debug info
        contour_pts: list[list[list[int]]] = []
        if not fallback:
            for cnt in raw_contours:
                contour_pts.append(cnt.squeeze().tolist())

        debug_info = SnakeDebugInfo(
            anchor_bbox=[px1, py1, px2, py2],
            tile_bboxes=tile_bboxes,
            contour_points=contour_pts,
            crop_offset=(crop_x1, crop_y1),
            crop_size=(crop_x2 - crop_x1, crop_y2 - crop_y1),
            tiles=snake_tiles,
        )

        return _nms(all_detections, iou_threshold=0.45), debug_info


def _merge_overlapping_rects(
    rects: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """Merge rectangles that overlap significantly to avoid redundant tiles."""
    if len(rects) <= 1:
        return rects

    merged: list[tuple[int, int, int, int]] = []
    used = [False] * len(rects)

    for i, (x1, y1, w1, h1) in enumerate(rects):
        if used[i]:
            continue
        mx1, my1, mx2, my2 = x1, y1, x1 + w1, y1 + h1
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, (x2, y2, w2, h2) in enumerate(rects):
                if used[j]:
                    continue
                jx2, jy2 = x2 + w2, y2 + h2
                # Check overlap
                ox1, oy1 = max(mx1, x2), max(my1, y2)
                ox2, oy2 = min(mx2, jx2), min(my2, jy2)
                if ox1 < ox2 and oy1 < oy2:
                    # Merge
                    mx1 = min(mx1, x2)
                    my1 = min(my1, y2)
                    mx2 = max(mx2, jx2)
                    my2 = max(my2, jy2)
                    used[j] = True
                    changed = True
        merged.append((mx1, my1, mx2 - mx1, my2 - my1))

    return merged


def _iou(a: list[float], b: list[float]) -> float:
    """Compute intersection-over-union of two [x1, y1, x2, y2] boxes."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter) if (area_a + area_b - inter) > 0 else 0.0


def _nms(detections: list[Detection], iou_threshold: float = 0.45) -> list[Detection]:
    """Non-max suppression: keep highest-confidence detection per overlap group."""
    if len(detections) <= 1:
        return detections

    # Sort by confidence descending
    dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    keep: list[Detection] = []
    for det in dets:
        if any(_iou(det.bbox, k.bbox) >= iou_threshold for k in keep):
            continue
        keep.append(det)
    return keep
