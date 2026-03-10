"""Action registry and dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

from couch_hound.actions.base import BaseAction

if TYPE_CHECKING:
    from couch_hound.config import ActionConfig

ACTION_REGISTRY: dict[str, type[BaseAction]] = {}


def create_action(config: ActionConfig) -> BaseAction:
    """Instantiate an action from its config, using the type registry."""
    cls = ACTION_REGISTRY.get(config.type)
    if cls is None:
        raise NotImplementedError(f"Action type '{config.type}' is not implemented")
    return cls(config)


def _register_actions() -> None:
    """Import action modules to populate the registry."""
    from couch_hound.actions.script import ScriptAction

    ACTION_REGISTRY["script"] = ScriptAction


_register_actions()
