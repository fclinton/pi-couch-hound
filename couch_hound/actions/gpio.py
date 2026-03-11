"""GPIO action — drives a Raspberry Pi GPIO pin."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from couch_hound.actions.base import BaseAction

try:
    import RPi.GPIO as _GPIO  # type: ignore[import-untyped]
except ImportError:
    _GPIO = None


class GpioAction(BaseAction):
    """Control a GPIO pin in pulse, toggle, or momentary mode."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Drive the configured GPIO pin."""
        if _GPIO is None:
            raise RuntimeError("RPi.GPIO is not available (not running on a Raspberry Pi?)")

        pin = self.config.pin
        if pin is None:
            raise RuntimeError("GPIO pin number not configured")

        mode = self.config.mode or "pulse"
        duration = self.config.duration or 1.0

        await asyncio.to_thread(self._drive_pin, pin, mode, duration)

    @staticmethod
    def _drive_pin(pin: int, mode: str, duration: float) -> None:
        """Blocking GPIO pin control."""
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
