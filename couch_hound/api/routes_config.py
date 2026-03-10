"""Configuration CRUD endpoints with validation, persistence, and hot-reload."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from couch_hound.config import AppConfig, save_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])

SECTION_FIELDS = frozenset(AppConfig.model_fields.keys())


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Return the full current configuration as JSON."""
    config: AppConfig = request.app.state.config
    return config.model_dump(mode="json")


@router.put("/config")
async def replace_config(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Replace the entire configuration, validate, persist to YAML, and hot-reload."""
    try:
        new_config = AppConfig(**body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    save_config(new_config, request.app.state.config_path)
    request.app.state.config = new_config
    logger.info("Full config replaced and hot-reloaded")
    return new_config.model_dump(mode="json")


@router.patch("/config/{section}")
async def patch_config_section(
    section: str, body: dict[str, Any], request: Request
) -> dict[str, Any]:
    """Partially update a config section and hot-reload.

    Valid sections: camera, detection, cooldown, actions, web, logging.
    """
    if section not in SECTION_FIELDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown config section '{section}'. "
            f"Valid sections: {', '.join(sorted(SECTION_FIELDS))}",
        )

    config: AppConfig = request.app.state.config
    current_data = config.model_dump(mode="json")

    # For list-typed sections (like actions), replace entirely rather than merge
    if isinstance(current_data[section], list):
        current_data[section] = body.get(section, body)
    elif isinstance(current_data[section], dict):
        current_data[section] = {**current_data[section], **body}
    else:
        current_data[section] = body

    try:
        new_config = AppConfig(**current_data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    save_config(new_config, request.app.state.config_path)
    request.app.state.config = new_config
    logger.info("Config section '%s' updated and hot-reloaded", section)
    return new_config.model_dump(mode="json")
