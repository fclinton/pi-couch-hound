"""Escalation manager — tracks detection persistence and fires tiered actions."""

from __future__ import annotations

import time

from couch_hound.config import EscalationConfig

# Number of consecutive no-detection cycles required before escalation state
# can reset. Detections flicker at the confidence-threshold boundary; without
# this debounce a single missed frame resets state and the next detected frame
# immediately re-fires every delay-0 level, spamming actions every cycle.
_RESET_DEBOUNCE_CYCLES = 3


class EscalationManager:
    """Track sustained detection and determine which escalation levels to fire."""

    def __init__(self, config: EscalationConfig) -> None:
        self._config = config
        self._initial_detection_time: float | None = None
        self._last_detection_time: float | None = None
        self._levels_fired: set[int] = set()
        self._consecutive_misses: int = 0

    def update_detection(self, detected: bool) -> list[int]:
        """Called each detection cycle. Returns list of level indices to fire now.

        Args:
            detected: Whether a valid detection was found this cycle.

        Returns:
            List of level indices (into config.levels) whose actions should fire.
        """
        now = time.monotonic()

        if not detected:
            return self._handle_no_detection(now)

        # Detection is active
        self._consecutive_misses = 0
        if self._initial_detection_time is None:
            self._initial_detection_time = now

        self._last_detection_time = now

        elapsed = now - self._initial_detection_time
        to_fire: list[int] = []

        for i, level in enumerate(self._config.levels):
            if i in self._levels_fired:
                continue
            if elapsed >= level.delay:
                to_fire.append(i)
                self._levels_fired.add(i)

        return to_fire

    def _handle_no_detection(self, now: float) -> list[int]:
        """Handle a cycle with no detection, potentially resetting state."""
        if self._initial_detection_time is None:
            return []

        self._consecutive_misses += 1

        if self._config.reset_cooldown == 0:
            # No time-based hysteresis configured — debounce by consecutive
            # cycles instead, so one flickered frame doesn't reset everything.
            if self._consecutive_misses >= _RESET_DEBOUNCE_CYCLES:
                self.reset()
            return []

        # Check if reset_cooldown has elapsed since last detection
        if self._last_detection_time is not None:
            since_last = now - self._last_detection_time
            if since_last >= self._config.reset_cooldown:
                self.reset()

        return []

    def get_context_vars(self, level_index: int) -> dict[str, str]:
        """Return escalation template variables for a given level.

        Args:
            level_index: Zero-based index of the escalation level being fired.

        Returns:
            Dict with escalation_level (1-indexed) and escalation_elapsed.
        """
        elapsed = 0.0
        if self._initial_detection_time is not None:
            elapsed = time.monotonic() - self._initial_detection_time

        return {
            "escalation_level": str(level_index + 1),
            "escalation_elapsed": f"{elapsed:.1f}",
        }

    def reset(self) -> None:
        """Reset escalation state back to initial."""
        self._initial_detection_time = None
        self._last_detection_time = None
        self._levels_fired.clear()
        self._consecutive_misses = 0

    def update_config(self, config: EscalationConfig) -> None:
        """Update config and reset state."""
        self._config = config
        self.reset()
