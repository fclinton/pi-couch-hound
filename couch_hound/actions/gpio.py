"""GPIO action — drives a Raspberry Pi GPIO pin.

Prefers gpiozero (works on RPi 5 and older models).  Falls back to RPi.GPIO
for legacy setups.  Raises at runtime if neither library is installed.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from couch_hound.actions.base import BaseAction

try:
    from gpiozero import DigitalOutputDevice as _DigitalOutputDevice
except ImportError:
    _DigitalOutputDevice = None

try:
    import RPi.GPIO as _GPIO  # type: ignore[import-untyped]
except ImportError:
    _GPIO = None


class GpioAction(BaseAction):
    """Control a GPIO pin in pulse, toggle, or momentary mode."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Drive the configured GPIO pin."""
        if _DigitalOutputDevice is None and _GPIO is None:
            raise RuntimeError(
                "Neither gpiozero nor RPi.GPIO is available (not running on a Raspberry Pi?)"
            )

        pin = self.config.pin
        if pin is None:
            raise RuntimeError("GPIO pin number not configured")

        mode = self.config.mode or "pulse"
        duration = self.config.duration or 1.0

        await asyncio.to_thread(self._drive_pin, pin, mode, duration)

    @staticmethod
    def _drive_pin(pin: int, mode: str, duration: float) -> None:
        """Dispatch to the available GPIO backend.

        Tries gpiozero first.  If it fails at the hardware level (e.g. wrong
        pin factory on an RPi 5 without lgpio), falls back to RPi.GPIO.
        """
        if _DigitalOutputDevice is not None:
            try:
                GpioAction._drive_pin_gpiozero(pin, mode, duration)
                return
            except RuntimeError:
                if _GPIO is None:
                    raise
        if _GPIO is not None:
            GpioAction._drive_pin_rpigpio(pin, mode, duration)
        else:
            raise RuntimeError("No working GPIO backend available")

    @staticmethod
    def _drive_pin_gpiozero(pin: int, mode: str, duration: float) -> None:
        """Drive a pin using gpiozero."""
        assert _DigitalOutputDevice is not None
        dev = _DigitalOutputDevice(pin)
        try:
            if mode in ("pulse", "momentary"):
                dev.on()
                time.sleep(duration)
                dev.off()
            elif mode == "toggle":
                dev.toggle()
            else:
                raise RuntimeError(f"Unknown GPIO mode: {mode}")
        finally:
            if mode in ("pulse", "momentary"):
                dev.off()
            dev.close()

    @staticmethod
    def _drive_pin_rpigpio(pin: int, mode: str, duration: float) -> None:
        """Drive a pin using RPi.GPIO (legacy fallback)."""
        assert _GPIO is not None
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setup(pin, _GPIO.OUT)

        try:
            if mode in ("pulse", "momentary"):
                _GPIO.output(pin, _GPIO.HIGH)
                time.sleep(duration)
                _GPIO.output(pin, _GPIO.LOW)
            elif mode == "toggle":
                current = _GPIO.input(pin)
                _GPIO.output(pin, not current)
            else:
                raise RuntimeError(f"Unknown GPIO mode: {mode}")
        finally:
            if mode in ("pulse", "momentary"):
                _GPIO.output(pin, _GPIO.LOW)
