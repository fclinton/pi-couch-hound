"""Script action — runs a shell command in a subprocess."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from couch_hound.actions.base import BaseAction


class ScriptAction(BaseAction):
    """Run an arbitrary shell command with a configurable timeout."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Execute the configured command in a subprocess."""
        command = self.config.command or ""
        timeout = self.config.timeout or 30
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as exc:
            proc.kill()
            raise RuntimeError(f"Script timed out after {timeout}s") from exc
        if proc.returncode != 0:
            raise RuntimeError(f"Script exited with code {proc.returncode}")
