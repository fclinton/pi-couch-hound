"""Base class for all action types."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from couch_hound.config import ActionConfig

logger = logging.getLogger(__name__)


class BaseAction(ABC):
    """Abstract base class for detection actions."""

    def __init__(self, config: ActionConfig) -> None:
        self.config = config
        self.name = config.name

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> None:
        """Execute the action with the given detection context."""

    async def _retry(
        self,
        coro_factory: Callable[[], Awaitable[None]],
        *,
        max_attempts: int = 2,
        delay: float = 1.0,
    ) -> None:
        """Retry an async operation up to *max_attempts* times."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                await coro_factory()
                return
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning("Action '%s' attempt %d failed: %s", self.name, attempt + 1, exc)
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
