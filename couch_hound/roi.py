"""Region-of-interest geometry — check bounding box overlap with a polygon."""

from __future__ import annotations


def _polygon_area(vertices: list[list[float]]) -> float:
    """Compute area of a polygon using the shoelace formula."""
    n = len(vertices)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0


def _clip_polygon_by_edge(
    polygon: list[list[float]],
    edge_start: list[float],
    edge_end: list[float],
) -> list[list[float]]:
    """Clip a polygon against a single edge using Sutherland-Hodgman."""
    if not polygon:
        return []

    def inside(point: list[float]) -> bool:
        return (
            (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1])
            - (edge_end[1] - edge_start[1]) * (point[0] - edge_start[0])
        ) >= 0

    def intersection(p1: list[float], p2: list[float]) -> list[float]:
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = edge_start
        x4, y4 = edge_end
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-12:
            return p1
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        return [x1 + t * (x2 - x1), y1 + t * (y2 - y1)]

    output: list[list[float]] = []
    for i in range(len(polygon)):
        current = polygon[i]
        next_pt = polygon[(i + 1) % len(polygon)]
        curr_inside = inside(current)
        next_inside = inside(next_pt)

        if curr_inside:
            output.append(current)
            if not next_inside:
                output.append(intersection(current, next_pt))
        elif next_inside:
            output.append(intersection(current, next_pt))

    return output


def _clip_polygon_by_polygon(
    subject: list[list[float]],
    clip: list[list[float]],
) -> list[list[float]]:
    """Sutherland-Hodgman polygon clipping."""
    output = list(subject)
    for i in range(len(clip)):
        if not output:
            break
        edge_start = clip[i]
        edge_end = clip[(i + 1) % len(clip)]
        output = _clip_polygon_by_edge(output, edge_start, edge_end)
    return output


def bbox_in_roi(
    bbox: list[float],
    polygon: list[list[float]],
    min_overlap: float,
) -> bool:
    """Check if a bounding box overlaps a polygon ROI by at least min_overlap.

    Args:
        bbox: Bounding box as [x1, y1, x2, y2] in normalized coords (0-1).
        polygon: ROI polygon as [[x, y], ...] in normalized coords (0-1).
        min_overlap: Minimum fraction of bbox area that must overlap (0.0-1.0).

    Returns:
        True if the overlap ratio meets or exceeds min_overlap.
    """
    x1, y1, x2, y2 = bbox
    bbox_area = (x2 - x1) * (y2 - y1)
    if bbox_area <= 0:
        return False

    bbox_poly: list[list[float]] = [
        [x1, y1],
        [x2, y1],
        [x2, y2],
        [x1, y2],
    ]

    clipped = _clip_polygon_by_polygon(bbox_poly, polygon)
    if len(clipped) < 3:
        return False

    intersection_area = _polygon_area(clipped)
    return (intersection_area / bbox_area) >= min_overlap
