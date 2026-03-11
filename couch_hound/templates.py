"""Template variable rendering for action configuration strings."""

from __future__ import annotations

import re


def render_template(template: str, context: dict[str, str]) -> str:
    """Replace {{variable}} placeholders with values from context."""

    def replacer(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return context.get(key, "")

    return re.sub(r"\{\{(\w+)\}\}", replacer, template)


def build_context(
    *,
    label: str,
    confidence: float,
    bbox: list[float],
    timestamp: str,
    snapshot_path: str = "",
) -> dict[str, str]:
    """Build a template context dict from detection results."""
    return {
        "timestamp": timestamp,
        "confidence": f"{confidence:.4f}",
        "label": label,
        "bbox": str(bbox),
        "snapshot_path": snapshot_path,
    }
