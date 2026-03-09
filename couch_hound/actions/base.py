"""Base class for all action types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from couch_hound.config import ActionConfig


class BaseAction(ABC):
    """Abstract base class for detection actions."""

    def __init__(self, config: ActionConfig) -> None:
        self.config = config
        self.name = config.name

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> None:
        """Execute the action with the given detection context."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
