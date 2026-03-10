"""Configuration loading, validation, persistence, and hot-reload."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config.yaml")
CONFIG_EXAMPLE_PATH = Path("config.example.yaml")


class CameraConfig(BaseModel):
    source: int | str = 0
    resolution: list[int] = Field(default=[1280, 720])
    capture_interval: float = Field(default=0.5, ge=0.1, le=5.0)


class RoiConfig(BaseModel):
    enabled: bool = False
    polygon: list[list[float]] = Field(default=[[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]])
    min_overlap: float = Field(default=0.3, ge=0.0, le=1.0)


class DetectionConfig(BaseModel):
    model: str = "models/ssd_mobilenet_v2.tflite"
    labels: str = "models/coco_labels.txt"
    target_label: str = "dog"
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    use_coral: bool = False
    roi: RoiConfig = Field(default_factory=RoiConfig)


class CooldownConfig(BaseModel):
    seconds: int = Field(default=30, ge=0, le=300)


class ActionConfig(BaseModel):
    name: str
    type: Literal["sound", "snapshot", "http", "mqtt", "script", "gpio"]
    enabled: bool = True
    # Sound
    sound_file: str | None = None
    volume: int | None = Field(default=None, ge=0, le=100)
    # Snapshot
    save_dir: str | None = None
    max_kept: int | None = None
    # HTTP
    url: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None
    body: str | None = None
    # MQTT
    broker: str | None = None
    port: int | None = None
    topic: str | None = None
    payload: str | None = None
    # Script
    command: str | None = None
    timeout: int | None = None
    # GPIO
    pin: int | None = None
    mode: Literal["pulse", "toggle", "momentary"] | None = None
    duration: float | None = None


class AuthConfig(BaseModel):
    enabled: bool = False
    username: str = "admin"
    password_hash: str = ""


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    auth: AuthConfig = Field(default_factory=AuthConfig)


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = "logs/couch-hound.log"
    max_size_mb: int = 50
    backup_count: int = 3


class AppConfig(BaseModel):
    camera: CameraConfig = Field(default_factory=CameraConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    cooldown: CooldownConfig = Field(default_factory=CooldownConfig)
    actions: list[ActionConfig] = Field(default_factory=list)
    web: WebConfig = Field(default_factory=WebConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from YAML file."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        logger.warning("Config file not found at %s, using defaults", config_path)
        return AppConfig()

    with open(config_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    return AppConfig(**raw)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Persist configuration to YAML file."""
    config_path = path or CONFIG_PATH
    data = config.model_dump(mode="json")
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    logger.info("Configuration saved to %s", config_path)
