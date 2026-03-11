"""Tests for the cooldown manager."""

from __future__ import annotations

from unittest.mock import patch

from couch_hound.config import CooldownConfig
from couch_hound.cooldown import CooldownManager


class TestCooldownManager:
    def test_first_trigger_always_allowed(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=30))
        assert mgr.can_trigger() is True

    def test_trigger_blocked_during_cooldown(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=30))
        with patch("couch_hound.cooldown.time.monotonic", return_value=100.0):
            mgr.record_trigger()
        with patch("couch_hound.cooldown.time.monotonic", return_value=110.0):
            assert mgr.can_trigger() is False

    def test_trigger_allowed_after_cooldown(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=30))
        with patch("couch_hound.cooldown.time.monotonic", return_value=100.0):
            mgr.record_trigger()
        with patch("couch_hound.cooldown.time.monotonic", return_value=131.0):
            assert mgr.can_trigger() is True

    def test_zero_cooldown_always_allows(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=0))
        mgr.record_trigger()
        assert mgr.can_trigger() is True

    def test_reset_clears_state(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=300))
        mgr.record_trigger()
        mgr.reset()
        assert mgr.can_trigger() is True

    def test_update_config(self) -> None:
        mgr = CooldownManager(CooldownConfig(seconds=300))
        with patch("couch_hound.cooldown.time.monotonic", return_value=100.0):
            mgr.record_trigger()
        mgr.update_config(CooldownConfig(seconds=5))
        with patch("couch_hound.cooldown.time.monotonic", return_value=106.0):
            assert mgr.can_trigger() is True
