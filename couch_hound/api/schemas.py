"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    uptime_seconds: float
    version: str


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
