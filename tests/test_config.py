"""Tests for configuration loading and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from couch_hound.config import (
    AppConfig,
    EscalationConfig,
    EscalationLevelConfig,
    MonitoringConfig,
    UpdateConfig,
    load_config,
    migrate_config,
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


def test_default_update_config():
    """Default update config should be disabled."""
    config = AppConfig()
    assert config.update.enabled is False
    assert config.update.check_interval_minutes == 60
    assert config.update.auto_apply is False
    assert config.update.maintenance_window_start is None
    assert config.update.maintenance_window_end is None


def test_update_config_interval_range():
    """Check interval should be constrained between 5 and 1440 minutes."""
    import pytest

    with pytest.raises(Exception):
        UpdateConfig(check_interval_minutes=2)

    with pytest.raises(Exception):
        UpdateConfig(check_interval_minutes=1500)

    config = UpdateConfig(check_interval_minutes=120)
    assert config.check_interval_minutes == 120


def test_update_config_window_format():
    """Maintenance window fields must be HH:MM format."""
    import pytest

    config = UpdateConfig(maintenance_window_start="03:00", maintenance_window_end="05:00")
    assert config.maintenance_window_start == "03:00"

    with pytest.raises(Exception):
        UpdateConfig(maintenance_window_start="3:00")

    with pytest.raises(Exception):
        UpdateConfig(maintenance_window_start="abc")


def test_update_config_roundtrip():
    """Update config should round-trip through YAML."""
    config = AppConfig(
        update=UpdateConfig(
            enabled=True,
            check_interval_minutes=30,
            auto_apply=True,
            maintenance_window_start="02:00",
            maintenance_window_end="04:00",
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    save_config(config, path)
    loaded = load_config(path)
    assert loaded.update.enabled is True
    assert loaded.update.check_interval_minutes == 30
    assert loaded.update.auto_apply is True
    assert loaded.update.maintenance_window_start == "02:00"
    assert loaded.update.maintenance_window_end == "04:00"
    path.unlink()


def test_load_config_ignores_unknown_fields():
    """Loading a config with unknown fields should not raise."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        yaml.dump({"web": {"port": 9090}, "unknown_section": {"foo": "bar"}}, f)
        path = Path(f.name)

    config = load_config(path)
    assert config.web.port == 9090
    path.unlink()


def test_migrate_config_adds_new_keys(tmp_path: Path):
    """migrate_config should add keys from example that are missing in user config."""
    config_path = tmp_path / "config.yaml"
    example_path = tmp_path / "config.example.yaml"

    user_data = {"web": {"port": 9090}}
    example_data = {"web": {"port": 8080, "host": "0.0.0.0"}, "cooldown": {"seconds": 30}}

    with open(config_path, "w") as f:
        yaml.dump(user_data, f)
    with open(example_path, "w") as f:
        yaml.dump(example_data, f)

    added = migrate_config(tmp_path)

    assert "web.host" in added
    assert "cooldown" in added

    with open(config_path) as f:
        result = yaml.safe_load(f)

    # User's existing value preserved
    assert result["web"]["port"] == 9090
    # New keys added from example
    assert result["web"]["host"] == "0.0.0.0"
    assert result["cooldown"] == {"seconds": 30}


def test_migrate_config_preserves_existing(tmp_path: Path):
    """migrate_config should not overwrite existing user values."""
    config_path = tmp_path / "config.yaml"
    example_path = tmp_path / "config.example.yaml"

    user_data = {"web": {"port": 9090, "host": "127.0.0.1"}, "cooldown": {"seconds": 60}}
    example_data = {"web": {"port": 8080, "host": "0.0.0.0"}, "cooldown": {"seconds": 30}}

    with open(config_path, "w") as f:
        yaml.dump(user_data, f)
    with open(example_path, "w") as f:
        yaml.dump(example_data, f)

    added = migrate_config(tmp_path)

    assert added == []

    with open(config_path) as f:
        result = yaml.safe_load(f)

    assert result["web"]["port"] == 9090
    assert result["web"]["host"] == "127.0.0.1"
    assert result["cooldown"]["seconds"] == 60
