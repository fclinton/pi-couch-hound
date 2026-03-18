"""Tests for the ChromecastAction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from couch_hound.actions.chromecast import ChromecastAction, _guess_audio_type
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_cast", type="chromecast", **kwargs)


async def test_cast_success() -> None:
    config = _make_config(
        device_name="Living Room",
        media_url="http://example.com/alert.mp3",
        volume=60,
    )
    action = ChromecastAction(config)

    with patch.object(ChromecastAction, "_cast") as mock_cast:
        await action.execute({})
        mock_cast.assert_called_once_with(
            "Living Room",
            "http://example.com/alert.mp3",
            0.6,
        )


async def test_cast_default_volume() -> None:
    config = _make_config(
        device_name="Living Room",
        media_url="http://example.com/alert.mp3",
    )
    action = ChromecastAction(config)

    with patch.object(ChromecastAction, "_cast") as mock_cast:
        await action.execute({})
        mock_cast.assert_called_once_with(
            "Living Room",
            "http://example.com/alert.mp3",
            0.8,
        )


async def test_cast_no_device_name() -> None:
    config = _make_config(media_url="http://example.com/alert.mp3")
    action = ChromecastAction(config)

    with pytest.raises(RuntimeError, match="No Chromecast device_name configured"):
        await action.execute({})


async def test_cast_no_media() -> None:
    config = _make_config(device_name="Living Room")
    action = ChromecastAction(config)

    with pytest.raises(RuntimeError, match="No media_url or sound_file configured"):
        await action.execute({})


async def test_cast_with_sound_file() -> None:
    config = _make_config(device_name="Living Room", sound_file="/sounds/alert.mp3")
    action = ChromecastAction(config)

    with (
        patch.object(ChromecastAction, "_cast") as mock_cast,
        patch("couch_hound.actions.chromecast.socket") as mock_socket,
    ):
        mock_socket.gethostbyname.return_value = "192.168.1.10"
        mock_socket.gethostname.return_value = "pi"
        await action.execute({})
        call_args = mock_cast.call_args[0]
        assert call_args[0] == "Living Room"
        assert "192.168.1.10" in call_args[1]
        assert "/media/" in call_args[1]
        assert "alert.mp3" in call_args[1]
        assert call_args[1].startswith("http://")


async def test_cast_media_url_preferred_over_sound_file() -> None:
    config = _make_config(
        device_name="Living Room",
        media_url="http://example.com/custom.mp3",
        sound_file="/sounds/alert.mp3",
    )
    action = ChromecastAction(config)

    with patch.object(ChromecastAction, "_cast") as mock_cast:
        await action.execute({})
        call_args = mock_cast.call_args[0]
        assert call_args[1] == "http://example.com/custom.mp3"


async def test_cast_device_not_found() -> None:
    mock_browser = MagicMock()
    with patch("pychromecast.get_listed_chromecasts", return_value=([], mock_browser)):
        with pytest.raises(RuntimeError, match="not found on network"):
            ChromecastAction._cast("Missing Device", "http://example.com/a.mp3", 0.5)


def test_guess_audio_type_mp3() -> None:
    assert _guess_audio_type("http://host/file.mp3") == "audio/mpeg"


def test_guess_audio_type_wav() -> None:
    result = _guess_audio_type("http://host/file.wav")
    assert result in ("audio/wav", "audio/x-wav")


def test_guess_audio_type_ogg() -> None:
    assert _guess_audio_type("http://host/file.ogg") == "audio/ogg"


def test_guess_audio_type_unknown() -> None:
    assert _guess_audio_type("http://host/file.xyz") == "audio/mpeg"
