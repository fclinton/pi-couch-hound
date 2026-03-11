"""Cooldown manager — prevents action spam by enforcing minimum intervals."""

from __future__ import annotations

import time

from couch_hound.config import CooldownConfig


class CooldownManager:
    """Track elapsed time between detection triggers."""

    def __init__(self, config: CooldownConfig) -> None:
        self._seconds = config.seconds
        self._last_trigger: float | None = None

    def can_trigger(self) -> bool:
        """Return True if cooldown has elapsed since the last trigger."""
        if self._seconds == 0:
            return True
        if self._last_trigger is None:
            return True
        return (time.monotonic() - self._last_trigger) >= self._seconds

    def record_trigger(self) -> None:
        """Record the current time as the last trigger."""
        self._last_trigger = time.monotonic()

    def reset(self) -> None:
        """Clear the last trigger time."""
        self._last_trigger = None

    def update_config(self, config: CooldownConfig) -> None:
        """Update the cooldown duration from new config."""
        self._seconds = config.seconds
