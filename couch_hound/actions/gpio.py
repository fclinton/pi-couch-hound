"""GPIO action — drives a Raspberry Pi GPIO pin via gpiozero.

Uses gpiozero with lgpio, which works on all Pi models including RPi 5.
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


class GpioAction(BaseAction):
    """Control a GPIO pin in pulse, toggle, or momentary mode."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Drive the configured GPIO pin."""
        if _DigitalOutputDevice is None:
            raise RuntimeError(
                "gpiozero is not available — install with: pip install 'pi-couch-hound[gpio]'"
            )

        pin = self.config.pin
        if pin is None:
            raise RuntimeError("GPIO pin number not configured")

        mode = self.config.mode or "pulse"
        duration = self.config.duration or 1.0

        await asyncio.to_thread(self._drive_pin, pin, mode, duration)

    @staticmethod
    def _drive_pin(pin: int, mode: str, duration: float) -> None:
        """Drive the configured GPIO pin using gpiozero."""
        assert _DigitalOutputDevice is not None
        try:
            dev = _DigitalOutputDevice(pin)
        except Exception as exc:
            if "BadPinFactory" in type(exc).__name__ or "pin factory" in str(exc).lower():
                raise RuntimeError(
                    "gpiozero has no working pin factory — "
                    "install lgpio: pip install 'pi-couch-hound[gpio]'"
                ) from exc
            raise
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
