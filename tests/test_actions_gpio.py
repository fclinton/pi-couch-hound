"""Tests for the GpioAction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import couch_hound.actions.gpio as gpio_mod
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_gpio", type="gpio", **kwargs)


# ---------------------------------------------------------------------------
# execute() – high-level tests (mock _drive_pin entirely)
# ---------------------------------------------------------------------------


async def test_gpio_pulse_mode() -> None:
    """Test that pulse mode calls _drive_pin with correct args."""
    config = _make_config(pin=17, mode="pulse", duration=2.0)
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=MagicMock()):
        with patch.object(gpio_mod.GpioAction, "_drive_pin") as mock_drive:
            await action.execute({})
            mock_drive.assert_called_once_with(17, "pulse", 2.0)


async def test_gpio_toggle_mode() -> None:
    """Test that toggle mode calls _drive_pin with correct args."""
    config = _make_config(pin=17, mode="toggle")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=MagicMock()):
        with patch.object(gpio_mod.GpioAction, "_drive_pin") as mock_drive:
            await action.execute({})
            mock_drive.assert_called_once_with(17, "toggle", 1.0)


async def test_gpio_not_available() -> None:
    """Error when gpiozero is not installed."""
    config = _make_config(pin=17, mode="pulse")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=None):
        with pytest.raises(RuntimeError, match="gpiozero is not available"):
            await action.execute({})


async def test_gpio_no_pin_configured() -> None:
    config = _make_config(mode="pulse")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=MagicMock()):
        with pytest.raises(RuntimeError, match="GPIO pin number not configured"):
            await action.execute({})


# ---------------------------------------------------------------------------
# _drive_pin – gpiozero backend
# ---------------------------------------------------------------------------


async def test_gpio_drive_pin_pulse() -> None:
    """Pulse mode: on, sleep, off, close."""
    mock_dev = MagicMock()
    mock_cls = MagicMock(return_value=mock_dev)

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls),
        patch("time.sleep") as mock_sleep,
    ):
        gpio_mod.GpioAction._drive_pin(17, "pulse", 2.0)

    mock_cls.assert_called_once_with(17)
    mock_dev.on.assert_called()
    mock_sleep.assert_called_once_with(2.0)
    mock_dev.off.assert_called()
    mock_dev.close.assert_called_once()


async def test_gpio_drive_pin_toggle() -> None:
    """Toggle mode: toggle, close."""
    mock_dev = MagicMock()
    mock_cls = MagicMock(return_value=mock_dev)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    mock_cls.assert_called_once_with(17)
    mock_dev.toggle.assert_called_once()
    mock_dev.close.assert_called_once()


async def test_gpio_drive_pin_unknown_mode() -> None:
    """Unknown mode raises RuntimeError and still closes the device."""
    mock_dev = MagicMock()
    mock_cls = MagicMock(return_value=mock_dev)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls):
        with pytest.raises(RuntimeError, match="Unknown GPIO mode"):
            gpio_mod.GpioAction._drive_pin(17, "bad", 1.0)

    mock_dev.close.assert_called_once()


async def test_gpio_bad_pin_factory() -> None:
    """Clear error when gpiozero has no working pin factory (lgpio missing)."""

    class _BadPinFactoryError(Exception):  # noqa: N818
        pass

    mock_cls = MagicMock(side_effect=_BadPinFactoryError("Unable to load any default pin factory!"))

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls):
        with pytest.raises(RuntimeError, match="no working pin factory"):
            gpio_mod.GpioAction._drive_pin(17, "pulse", 1.0)
