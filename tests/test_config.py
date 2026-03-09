"""Tests for configuration loading and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from couch_hound.config import AppConfig, load_config, save_config


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
