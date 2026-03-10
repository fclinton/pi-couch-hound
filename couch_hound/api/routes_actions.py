"""Actions CRUD endpoints — list, create, update, delete, test-fire, and toggle."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from couch_hound.actions import create_action
from couch_hound.api.schemas import ActionTestResponse, ActionToggleResponse
from couch_hound.config import ActionConfig, AppConfig, save_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["actions"])


def _find_action(config: AppConfig, name: str) -> tuple[int, ActionConfig]:
    """Look up an action by name, raising 404 if not found."""
    for i, action in enumerate(config.actions):
        if action.name == name:
            return i, action
    raise HTTPException(status_code=404, detail=f"Action '{name}' not found")


@router.get("/actions")
async def list_actions(request: Request) -> list[dict[str, Any]]:
    """Return all configured actions."""
    config: AppConfig = request.app.state.config
    return [a.model_dump(mode="json") for a in config.actions]


@router.post("/actions", status_code=201)
async def create_action_endpoint(action: ActionConfig, request: Request) -> dict[str, Any]:
    """Create a new action. Returns 409 if the name already exists."""
    config: AppConfig = request.app.state.config
    for existing in config.actions:
        if existing.name == action.name:
            raise HTTPException(
                status_code=409,
                detail=f"Action with name '{action.name}' already exists",
            )
    config.actions.append(action)
    save_config(config, request.app.state.config_path)
    request.app.state.config = config
    logger.info("Action '%s' created", action.name)
    return action.model_dump(mode="json")


@router.put("/actions/{name}")
async def update_action(name: str, action: ActionConfig, request: Request) -> dict[str, Any]:
    """Update an existing action by name. Supports renaming with conflict check."""
    config: AppConfig = request.app.state.config
    idx, _ = _find_action(config, name)
    # If renaming, check the new name isn't taken by another action
    if action.name != name:
        for i, existing in enumerate(config.actions):
            if existing.name == action.name and i != idx:
                raise HTTPException(
                    status_code=409,
                    detail=f"Action with name '{action.name}' already exists",
                )
    config.actions[idx] = action
    save_config(config, request.app.state.config_path)
    request.app.state.config = config
    logger.info("Action '%s' updated", name)
    return action.model_dump(mode="json")


@router.delete("/actions/{name}", status_code=204)
async def delete_action(name: str, request: Request) -> Response:
    """Remove an action by name."""
    config: AppConfig = request.app.state.config
    idx, _ = _find_action(config, name)
    config.actions.pop(idx)
    save_config(config, request.app.state.config_path)
    request.app.state.config = config
    logger.info("Action '%s' deleted", name)
    return Response(status_code=204)


@router.post("/actions/{name}/test")
async def test_fire_action(name: str, request: Request) -> ActionTestResponse:
    """Test-fire an action by name."""
    config: AppConfig = request.app.state.config
    _, action_cfg = _find_action(config, name)
    try:
        action = create_action(action_cfg)
        await action.execute({})
        return ActionTestResponse(name=name, success=True, message="Action executed successfully")
    except NotImplementedError as exc:
        return ActionTestResponse(name=name, success=False, message=str(exc))
    except Exception as exc:
        return ActionTestResponse(name=name, success=False, message=f"Action failed: {exc}")


@router.patch("/actions/{name}/toggle")
async def toggle_action(name: str, request: Request) -> ActionToggleResponse:
    """Toggle an action's enabled state."""
    config: AppConfig = request.app.state.config
    idx, action = _find_action(config, name)
    config.actions[idx] = action.model_copy(update={"enabled": not action.enabled})
    save_config(config, request.app.state.config_path)
    request.app.state.config = config
    logger.info("Action '%s' toggled to enabled=%s", name, config.actions[idx].enabled)
    return ActionToggleResponse(name=name, enabled=config.actions[idx].enabled)
