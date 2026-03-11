"""Tests for the GpioAction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import couch_hound.actions.gpio as gpio_mod
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_gpio", type="gpio", **kwargs)


async def test_gpio_pulse_mode() -> None:
    """Test that pulse mode calls _drive_pin with correct args."""
    config = _make_config(pin=17, mode="pulse", duration=2.0)
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_GPIO", new=MagicMock()):
        with patch.object(gpio_mod.GpioAction, "_drive_pin") as mock_drive:
            await action.execute({})
            mock_drive.assert_called_once_with(17, "pulse", 2.0)


async def test_gpio_toggle_mode() -> None:
    """Test that toggle mode calls _drive_pin with correct args."""
    config = _make_config(pin=17, mode="toggle")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_GPIO", new=MagicMock()):
        with patch.object(gpio_mod.GpioAction, "_drive_pin") as mock_drive:
            await action.execute({})
            mock_drive.assert_called_once_with(17, "toggle", 1.0)


async def test_gpio_drive_pin_pulse() -> None:
    """Unit test _drive_pin in pulse mode with a mocked GPIO module."""
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.OUT = 0
    mock_gpio.HIGH = 1
    mock_gpio.LOW = 0

    with patch.object(gpio_mod, "_GPIO", new=mock_gpio), patch("time.sleep"):
        gpio_mod.GpioAction._drive_pin(17, "pulse", 2.0)

    mock_gpio.setmode.assert_called_once_with(11)
    mock_gpio.setup.assert_called_once_with(17, 0)
    mock_gpio.output.assert_any_call(17, 1)
    mock_gpio.output.assert_any_call(17, 0)


async def test_gpio_drive_pin_toggle() -> None:
    """Unit test _drive_pin in toggle mode with a mocked GPIO module."""
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.OUT = 0
    mock_gpio.input.return_value = 0

    with patch.object(gpio_mod, "_GPIO", new=mock_gpio):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    mock_gpio.input.assert_called_once_with(17)
    mock_gpio.output.assert_any_call(17, True)


async def test_gpio_not_available() -> None:
    config = _make_config(pin=17, mode="pulse")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_GPIO", new=None):
        with pytest.raises(RuntimeError, match="RPi.GPIO is not available"):
            await action.execute({})


async def test_gpio_no_pin_configured() -> None:
    config = _make_config(mode="pulse")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_GPIO", new=MagicMock()):
        with pytest.raises(RuntimeError, match="GPIO pin number not configured"):
            await action.execute({})
