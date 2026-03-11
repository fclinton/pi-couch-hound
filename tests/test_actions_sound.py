"""Tests for the SoundAction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from couch_hound.actions.sound import SoundAction
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_sound", type="sound", **kwargs)


@pytest.fixture
def sound_file(tmp_path: Path) -> Path:
    """Create a dummy sound file."""
    p = tmp_path / "alert.wav"
    p.write_bytes(b"RIFF" + b"\x00" * 100)
    return p


async def test_play_sound_success(sound_file: Path) -> None:
    config = _make_config(sound_file=str(sound_file), volume=60)
    action = SoundAction(config)

    mock_sound = MagicMock()
    mock_channel = MagicMock()
    mock_channel.get_busy.side_effect = [True, False]
    mock_sound.play.return_value = mock_channel

    with (
        patch("couch_hound.actions.sound.SoundAction._play_sound") as mock_play,
    ):
        await action.execute({})
        mock_play.assert_called_once_with(str(sound_file), 0.6)


async def test_play_sound_default_volume(sound_file: Path) -> None:
    config = _make_config(sound_file=str(sound_file))
    action = SoundAction(config)

    with patch("couch_hound.actions.sound.SoundAction._play_sound") as mock_play:
        await action.execute({})
        mock_play.assert_called_once_with(str(sound_file), 0.8)


async def test_play_sound_file_not_found() -> None:
    config = _make_config(sound_file="/nonexistent/sound.wav")
    action = SoundAction(config)

    with pytest.raises(RuntimeError, match="Sound file not found"):
        await action.execute({})


async def test_play_sound_no_file_configured() -> None:
    config = _make_config()
    action = SoundAction(config)

    with pytest.raises(RuntimeError, match="Sound file not found"):
        await action.execute({})
