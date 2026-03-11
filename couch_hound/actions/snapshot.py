"""Snapshot action — saves detection frames as JPEG images."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from couch_hound.actions.base import BaseAction


class SnapshotAction(BaseAction):
    """Save the detection frame to disk and prune old snapshots."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Save frame as JPEG and prune if over max_kept."""
        frame = context.get("frame")
        if frame is None:
            raise RuntimeError("No frame available in detection context")

        save_dir = Path(self.config.save_dir or "snapshots")
        max_kept = self.config.max_kept

        snapshot_path = await asyncio.to_thread(self._save_and_prune, frame, save_dir, max_kept)
        context["snapshot_path"] = str(snapshot_path)

    @staticmethod
    def _save_and_prune(frame: Any, save_dir: Path, max_kept: int | None) -> Path:
        """Write JPEG to disk and remove oldest files if over limit."""
        import cv2

        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"detection_{timestamp}.jpg"
        filepath = save_dir / filename

        success, buf = cv2.imencode(".jpg", frame)
        if not success:
            raise RuntimeError("Failed to encode frame as JPEG")
        filepath.write_bytes(buf.tobytes())

        if max_kept is not None and max_kept > 0:
            existing = sorted(save_dir.glob("detection_*.jpg"))
            while len(existing) > max_kept:
                existing.pop(0).unlink()

        return filepath
