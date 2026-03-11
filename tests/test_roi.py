"""Tests for ROI geometry."""

from __future__ import annotations

from couch_hound.roi import bbox_in_roi


class TestBboxInRoi:
    """Test bounding box / polygon overlap checks."""

    # A simple square ROI covering the center of the frame
    SQUARE_ROI: list[list[float]] = [
        [0.2, 0.2],
        [0.8, 0.2],
        [0.8, 0.8],
        [0.2, 0.8],
    ]

    def test_bbox_fully_inside_polygon(self) -> None:
        bbox = [0.3, 0.3, 0.7, 0.7]
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.9) is True

    def test_bbox_fully_outside_polygon(self) -> None:
        bbox = [0.0, 0.0, 0.1, 0.1]
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.1) is False

    def test_partial_overlap_above_threshold(self) -> None:
        # bbox half inside the ROI
        bbox = [0.1, 0.3, 0.5, 0.7]  # 0.4 wide, 0.4 tall = area 0.16
        # Overlap: x from 0.2 to 0.5 = 0.3, y from 0.3 to 0.7 = 0.4 -> 0.12
        # Ratio: 0.12 / 0.16 = 0.75
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.7) is True

    def test_partial_overlap_below_threshold(self) -> None:
        bbox = [0.1, 0.3, 0.5, 0.7]
        # Same overlap ratio of 0.75
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.8) is False

    def test_zero_area_bbox_returns_false(self) -> None:
        bbox = [0.5, 0.5, 0.5, 0.5]
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.0) is False

    def test_zero_min_overlap_with_any_intersection(self) -> None:
        bbox = [0.1, 0.1, 0.3, 0.3]
        # Overlap: x 0.2-0.3=0.1, y 0.2-0.3=0.1 -> 0.01
        # Ratio: 0.01 / 0.04 = 0.25
        assert bbox_in_roi(bbox, self.SQUARE_ROI, min_overlap=0.0) is True

    def test_triangular_roi(self) -> None:
        triangle: list[list[float]] = [[0.5, 0.0], [1.0, 1.0], [0.0, 1.0]]
        bbox = [0.3, 0.5, 0.7, 0.9]
        # Triangle covers enough of the bbox
        assert bbox_in_roi(bbox, triangle, min_overlap=0.3) is True
