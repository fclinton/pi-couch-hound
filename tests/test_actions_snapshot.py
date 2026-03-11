"""Tests for the SnapshotAction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from couch_hound.actions.snapshot import SnapshotAction
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_snap", type="snapshot", **kwargs)


@pytest.fixture
def fake_frame() -> np.ndarray:
    """Create a small dummy frame."""
    return np.zeros((100, 100, 3), dtype=np.uint8)


async def test_save_snapshot(tmp_path: Path, fake_frame: np.ndarray) -> None:
    save_dir = tmp_path / "snaps"
    config = _make_config(save_dir=str(save_dir))
    action = SnapshotAction(config)

    context: dict[str, object] = {"frame": fake_frame}
    with patch("cv2.imencode") as mock_encode:
        mock_encode.return_value = (True, np.array([0xFF, 0xD8], dtype=np.uint8))
        await action.execute(context)

    assert "snapshot_path" in context
    assert save_dir.exists()


async def test_snapshot_prunes_old_files(tmp_path: Path, fake_frame: np.ndarray) -> None:
    save_dir = tmp_path / "snaps"
    save_dir.mkdir()

    # Pre-create 3 old snapshots
    for i in range(3):
        (save_dir / f"detection_old_{i:03d}.jpg").write_bytes(b"\xff")

    config = _make_config(save_dir=str(save_dir), max_kept=2)
    action = SnapshotAction(config)

    context: dict[str, object] = {"frame": fake_frame}
    with patch("cv2.imencode") as mock_encode:
        mock_encode.return_value = (True, np.array([0xFF, 0xD8], dtype=np.uint8))
        await action.execute(context)

    remaining = list(save_dir.glob("detection_*.jpg"))
    assert len(remaining) <= 2


async def test_snapshot_no_frame_raises() -> None:
    config = _make_config(save_dir="/tmp/snaps")
    action = SnapshotAction(config)

    with pytest.raises(RuntimeError, match="No frame available"):
        await action.execute({})


async def test_snapshot_encode_failure(tmp_path: Path, fake_frame: np.ndarray) -> None:
    config = _make_config(save_dir=str(tmp_path / "snaps"))
    action = SnapshotAction(config)

    context: dict[str, object] = {"frame": fake_frame}
    with (
        patch("cv2.imencode", return_value=(False, None)),
        pytest.raises(RuntimeError, match="Failed to encode"),
    ):
        await action.execute(context)
