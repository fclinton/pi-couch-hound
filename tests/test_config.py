"""Tests for configuration loading and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from couch_hound.config import (
    AppConfig,
    EscalationConfig,
    EscalationLevelConfig,
    MonitoringConfig,
    load_config,
    save_config,
)


def test_default_config():
    """Default config should have valid values."""
    config = AppConfig()
    assert config.web.port == 8080
    assert config.detection.confidence_threshold == 0.60
    assert config.cooldown.seconds == 30
    assert config.camera.capture_interval == 0.5


def test_load_config_missing_file():
    """Loading from non-existent file should return defaults."""
    config = load_config(Path("/nonexistent/config.yaml"))
    assert config.web.port == 8080


def test_save_and_load_config():
    """Config should round-trip through YAML."""
    config = AppConfig()
    config.web.port = 9090

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    save_config(config, path)
    loaded = load_config(path)
    assert loaded.web.port == 9090
    path.unlink()


def test_config_validation():
    """Invalid values should raise validation errors."""
    import pytest

    with pytest.raises(Exception):
        AppConfig(detection={"confidence_threshold": 2.0})  # type: ignore[arg-type]


def test_default_escalation_config():
    """Default escalation config should be disabled with empty levels."""
    config = AppConfig()
    assert config.escalation.enabled is False
    assert config.escalation.reset_cooldown == 0
    assert config.escalation.levels == []


def test_escalation_config_roundtrip():
    """Escalation config should round-trip through YAML."""
    config = AppConfig(
        escalation=EscalationConfig(
            enabled=True,
            reset_cooldown=10,
            levels=[
                EscalationLevelConfig(delay=0, actions=["bark"]),
                EscalationLevelConfig(delay=5, actions=["siren", "mqtt"]),
            ],
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    save_config(config, path)
    loaded = load_config(path)
    assert loaded.escalation.enabled is True
    assert loaded.escalation.reset_cooldown == 10
    assert len(loaded.escalation.levels) == 2
    assert loaded.escalation.levels[0].delay == 0
    assert loaded.escalation.levels[0].actions == ["bark"]
    assert loaded.escalation.levels[1].delay == 5
    assert loaded.escalation.levels[1].actions == ["siren", "mqtt"]
    path.unlink()


def test_escalation_max_levels():
    """Escalation levels should be capped at 5."""
    import pytest

    with pytest.raises(Exception):
        EscalationConfig(
            enabled=True,
            levels=[EscalationLevelConfig(delay=i) for i in range(6)],
        )


def test_default_monitoring_config():
    """Default monitoring config should be enabled with auto_disable off."""
    config = AppConfig()
    assert config.monitoring.enabled is True
    assert config.monitoring.auto_disable.person_detection is False


def test_monitoring_config_roundtrip():
    """Monitoring config should round-trip through YAML."""
    config = AppConfig(
        monitoring=MonitoringConfig(enabled=False),
    )

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    save_config(config, path)
    loaded = load_config(path)
    assert loaded.monitoring.enabled is False
    assert loaded.monitoring.auto_disable.person_detection is False
    path.unlink()
