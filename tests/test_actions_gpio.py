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
    """Error when neither library is installed."""
    config = _make_config(pin=17, mode="pulse")
    action = gpio_mod.GpioAction(config)

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=None),
        patch.object(gpio_mod, "_GPIO", new=None),
    ):
        with pytest.raises(RuntimeError, match="Neither gpiozero nor RPi.GPIO"):
            await action.execute({})


async def test_gpio_no_pin_configured() -> None:
    config = _make_config(mode="pulse")
    action = gpio_mod.GpioAction(config)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=MagicMock()):
        with pytest.raises(RuntimeError, match="GPIO pin number not configured"):
            await action.execute({})


# ---------------------------------------------------------------------------
# RPi.GPIO backend – _drive_pin_rpigpio
# ---------------------------------------------------------------------------


async def test_gpio_drive_pin_rpigpio_pulse() -> None:
    """Unit test _drive_pin_rpigpio in pulse mode."""
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.OUT = 0
    mock_gpio.HIGH = 1
    mock_gpio.LOW = 0

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=None),
        patch.object(gpio_mod, "_GPIO", new=mock_gpio),
        patch("time.sleep"),
    ):
        gpio_mod.GpioAction._drive_pin(17, "pulse", 2.0)

    mock_gpio.setmode.assert_called_once_with(11)
    mock_gpio.setup.assert_called_once_with(17, 0)
    mock_gpio.output.assert_any_call(17, 1)
    mock_gpio.output.assert_any_call(17, 0)


async def test_gpio_drive_pin_rpigpio_toggle() -> None:
    """Unit test _drive_pin_rpigpio in toggle mode."""
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.OUT = 0
    mock_gpio.input.return_value = 0

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=None),
        patch.object(gpio_mod, "_GPIO", new=mock_gpio),
    ):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    mock_gpio.input.assert_called_once_with(17)
    mock_gpio.output.assert_any_call(17, True)


# ---------------------------------------------------------------------------
# gpiozero backend – _drive_pin_gpiozero
# ---------------------------------------------------------------------------


async def test_gpio_drive_pin_gpiozero_pulse() -> None:
    """Unit test _drive_pin_gpiozero in pulse mode."""
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


async def test_gpio_drive_pin_gpiozero_toggle() -> None:
    """Unit test _drive_pin_gpiozero in toggle mode."""
    mock_dev = MagicMock()
    mock_cls = MagicMock(return_value=mock_dev)

    with patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    mock_cls.assert_called_once_with(17)
    mock_dev.toggle.assert_called_once()
    mock_dev.close.assert_called_once()


async def test_gpio_gpiozero_fallback_to_rpigpio() -> None:
    """When gpiozero raises RuntimeError, fall back to RPi.GPIO."""
    mock_cls = MagicMock(side_effect=RuntimeError("Cannot determine SOC peripheral base address"))
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.OUT = 0
    mock_gpio.input.return_value = 0

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls),
        patch.object(gpio_mod, "_GPIO", new=mock_gpio),
    ):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    # gpiozero was attempted
    mock_cls.assert_called_once_with(17)
    # RPi.GPIO was used as fallback
    mock_gpio.setmode.assert_called_once_with(11)
    mock_gpio.output.assert_any_call(17, True)


async def test_gpio_gpiozero_fails_no_fallback() -> None:
    """When gpiozero fails and RPi.GPIO is unavailable, error is raised."""
    mock_cls = MagicMock(side_effect=RuntimeError("Cannot determine SOC peripheral base address"))

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls),
        patch.object(gpio_mod, "_GPIO", new=None),
    ):
        with pytest.raises(RuntimeError, match="Cannot determine SOC"):
            gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)


async def test_gpio_prefers_gpiozero() -> None:
    """When both libraries are available, gpiozero is used."""
    mock_dev = MagicMock()
    mock_cls = MagicMock(return_value=mock_dev)
    mock_gpio = MagicMock()

    with (
        patch.object(gpio_mod, "_DigitalOutputDevice", new=mock_cls),
        patch.object(gpio_mod, "_GPIO", new=mock_gpio),
    ):
        gpio_mod.GpioAction._drive_pin(17, "toggle", 1.0)

    # gpiozero was used
    mock_cls.assert_called_once_with(17)
    # RPi.GPIO was NOT used
    mock_gpio.setmode.assert_not_called()
