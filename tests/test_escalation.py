"""Tests for the escalation manager."""

from __future__ import annotations

from unittest.mock import patch

from couch_hound.config import EscalationConfig, EscalationLevelConfig
from couch_hound.escalation import EscalationManager


def _make_config(
    *,
    reset_cooldown: int = 0,
    levels: list[EscalationLevelConfig] | None = None,
) -> EscalationConfig:
    if levels is None:
        levels = [
            EscalationLevelConfig(delay=0, actions=["alert"]),
            EscalationLevelConfig(delay=5, actions=["siren"]),
        ]
    return EscalationConfig(enabled=True, reset_cooldown=reset_cooldown, levels=levels)


class TestEscalationFireLevels:
    def test_first_detection_fires_level_zero(self) -> None:
        mgr = EscalationManager(_make_config())
        result = mgr.update_detection(True)
        assert result == [0]

    def test_subsequent_detection_within_delay_fires_nothing(self) -> None:
        mgr = EscalationManager(_make_config())
        mgr.update_detection(True)

        # Still within 5s delay for level 1
        result = mgr.update_detection(True)
        assert result == []

    def test_level_fires_after_delay(self) -> None:
        mgr = EscalationManager(_make_config())

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)

        # Advance past the 5s delay
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 5.0):
            result = mgr.update_detection(True)
        assert result == [1]

    def test_levels_dont_refire(self) -> None:
        mgr = EscalationManager(_make_config())

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 5.0):
            mgr.update_detection(True)

        # Level 0 and 1 already fired
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 10.0):
            result = mgr.update_detection(True)
        assert result == []

    def test_multiple_levels_can_fire_at_once(self) -> None:
        """If enough time passes, multiple levels fire in one cycle."""
        levels = [
            EscalationLevelConfig(delay=0, actions=["a"]),
            EscalationLevelConfig(delay=1, actions=["b"]),
            EscalationLevelConfig(delay=2, actions=["c"]),
        ]
        mgr = EscalationManager(_make_config(levels=levels))

        t = 100.0
        # First detection at t=100, then next check at t=105 (all levels due)
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            result1 = mgr.update_detection(True)
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 5.0):
            result2 = mgr.update_detection(True)

        assert result1 == [0]
        assert result2 == [1, 2]


class TestEscalationReset:
    def test_immediate_reset_on_no_detection(self) -> None:
        mgr = EscalationManager(_make_config(reset_cooldown=0))

        mgr.update_detection(True)
        mgr.update_detection(False)  # resets immediately

        # Should fire level 0 again since it was reset
        result = mgr.update_detection(True)
        assert result == [0]

    def test_delayed_reset_waits_for_cooldown(self) -> None:
        mgr = EscalationManager(_make_config(reset_cooldown=10))

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)

        # No detection but cooldown hasn't elapsed
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 3.0):
            mgr.update_detection(False)

        # Detection resumes — level 0 should NOT refire (not yet reset)
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 4.0):
            result = mgr.update_detection(True)
        assert result == []

    def test_delayed_reset_resets_after_cooldown(self) -> None:
        mgr = EscalationManager(_make_config(reset_cooldown=10))

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)

        # No detection, cooldown elapses
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 11.0):
            mgr.update_detection(False)

        # Detection resumes — level 0 should fire again
        with patch("couch_hound.escalation.time.monotonic", return_value=t + 12.0):
            result = mgr.update_detection(True)
        assert result == [0]

    def test_manual_reset(self) -> None:
        mgr = EscalationManager(_make_config())
        mgr.update_detection(True)

        mgr.reset()

        result = mgr.update_detection(True)
        assert result == [0]


class TestEscalationContextVars:
    def test_context_vars_level_1indexed(self) -> None:
        mgr = EscalationManager(_make_config())

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)

        with patch("couch_hound.escalation.time.monotonic", return_value=t + 3.0):
            ctx = mgr.get_context_vars(0)
        assert ctx["escalation_level"] == "1"
        assert ctx["escalation_elapsed"] == "3.0"

    def test_context_vars_level_2(self) -> None:
        mgr = EscalationManager(_make_config())

        t = 100.0
        with patch("couch_hound.escalation.time.monotonic", return_value=t):
            mgr.update_detection(True)

        with patch("couch_hound.escalation.time.monotonic", return_value=t + 5.5):
            ctx = mgr.get_context_vars(1)
        assert ctx["escalation_level"] == "2"
        assert ctx["escalation_elapsed"] == "5.5"


class TestEscalationUpdateConfig:
    def test_update_config_resets_state(self) -> None:
        mgr = EscalationManager(_make_config())
        mgr.update_detection(True)

        new_config = _make_config(reset_cooldown=5)
        mgr.update_config(new_config)

        # Should fire level 0 again since reset
        result = mgr.update_detection(True)
        assert result == [0]


class TestEscalationNoDetection:
    def test_no_detection_returns_empty(self) -> None:
        mgr = EscalationManager(_make_config())
        result = mgr.update_detection(False)
        assert result == []
