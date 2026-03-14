"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    uptime_seconds: float
    version: str
    detection_count: int
    last_detection_time: str | None
    monitoring_enabled: bool
    cpu_percent: float
    memory_percent: float
    temperature: float | None


class MonitoringToggleResponse(BaseModel):
    enabled: bool


class EventResponse(BaseModel):
    id: int
    timestamp: str
    confidence: float
    label: str
    bbox: list[float]
    snapshot_path: str | None = None
    actions_fired: list[str]


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
    limit: int
    offset: int


class ConfigUpdateRequest(BaseModel):
    """Partial config update."""

    data: dict[str, Any]


class ActionTestResponse(BaseModel):
    name: str
    success: bool
    message: str


class ActionToggleResponse(BaseModel):
    name: str
    enabled: bool


class SoundFileInfo(BaseModel):
    filename: str
    path: str
    size: int


class SoundListResponse(BaseModel):
    sounds: list[SoundFileInfo]


class SoundUploadResponse(BaseModel):
    filename: str
    path: str
    size: int


class ModelFileInfo(BaseModel):
    filename: str
    path: str
    size: int
    labels: str | None = None


class ModelListResponse(BaseModel):
    models: list[ModelFileInfo]


class ModelUploadResponse(BaseModel):
    model: str
    labels: str


class EventStatsResponse(BaseModel):
    total_events: int
    avg_confidence: float
    detections_per_hour: dict[str, int]
    detections_per_day: dict[str, int]
    peak_hour: int | None
    confidence_distribution: dict[str, int]


class RoiResponse(BaseModel):
    enabled: bool
    polygon: list[list[float]]
    min_overlap: float


class RoiUpdateRequest(BaseModel):
    polygon: list[list[float]]
    min_overlap: float | None = None


class ActionResultItem(BaseModel):
    name: str
    success: bool
    message: str


class TestAllActionsResponse(BaseModel):
    results: list[ActionResultItem]
    total: int
    succeeded: int
    failed: int


class RestartResponse(BaseModel):
    status: str
    message: str


# ── Auth ──


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    message: str


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    authenticated: bool
    username: str | None = None
