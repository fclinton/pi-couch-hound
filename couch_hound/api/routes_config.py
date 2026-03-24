"""Configuration CRUD endpoints with validation, persistence, and hot-reload."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from couch_hound.config import AppConfig, SslConfig, save_config
from couch_hound.pipeline import DetectionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])

SECTION_FIELDS = frozenset(AppConfig.model_fields.keys())

# Sections that require a full pipeline restart (camera re-open, model reload)
_RESTART_SECTIONS = frozenset({"camera", "detection"})
# Sections that require rebuilding action instances
_ACTIONS_SECTIONS = frozenset({"actions"})


async def _notify_pipeline(request: Request, changed_sections: set[str]) -> None:
    """Notify the pipeline of config changes with the appropriate reload strategy."""
    pipeline: DetectionPipeline = request.app.state.pipeline
    config: AppConfig = request.app.state.config
    if changed_sections & _RESTART_SECTIONS:
        pipeline.update_config(config)
        await pipeline.restart()
    elif changed_sections & _ACTIONS_SECTIONS:
        pipeline.update_config(config)
        pipeline.rebuild_actions()
    else:
        pipeline.update_config(config)


def _ssl_changed(old: SslConfig, new: SslConfig) -> bool:
    """Return True if SSL settings changed in a way that requires a server restart."""
    return old.model_dump() != new.model_dump()


def _schedule_restart() -> None:
    """Schedule a delayed process exit so the HTTP response can flush first.

    Systemd (Restart=always) will restart the process with the new config.
    Same pattern used by UpdateManager.apply_update.
    """
    loop = asyncio.get_running_loop()
    loop.call_later(2, os._exit, 75)
    logger.info("Server restart scheduled in 2 seconds for SSL config change")


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Return the full current configuration as JSON."""
    config: AppConfig = request.app.state.config
    return config.model_dump(mode="json")


@router.put("/config")
async def replace_config(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Replace the entire configuration, validate, persist to YAML, and hot-reload."""
    old_config = request.app.state.config
    old_ssl = old_config.web.ssl

    try:
        new_config = AppConfig(**body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    # Determine which sections changed
    old_data = old_config.model_dump(mode="json")
    new_data = new_config.model_dump(mode="json")
    changed = {key for key in SECTION_FIELDS if old_data.get(key) != new_data.get(key)}

    save_config(new_config, request.app.state.config_path)
    request.app.state.config = new_config
    logger.info("Full config replaced and persisted")

    if changed:
        await _notify_pipeline(request, changed)

    result = new_config.model_dump(mode="json")
    if _ssl_changed(old_ssl, new_config.web.ssl):
        result["_restart"] = True
        _schedule_restart()
    return result


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
    old_ssl = config.web.ssl
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
    logger.info("Config section '%s' updated and persisted", section)

    await _notify_pipeline(request, {section})

    result = new_config.model_dump(mode="json")
    if section == "web" and _ssl_changed(old_ssl, new_config.web.ssl):
        result["_restart"] = True
        _schedule_restart()
    return result
