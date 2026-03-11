"""Sound action — plays an audio file through the system audio output."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from couch_hound.actions.base import BaseAction


class SoundAction(BaseAction):
    """Play a WAV or MP3 file using pygame.mixer."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Play the configured sound file."""
        sound_file = self.config.sound_file or ""
        if not sound_file or not Path(sound_file).exists():
            raise RuntimeError(f"Sound file not found: {sound_file}")

        volume = (self.config.volume if self.config.volume is not None else 80) / 100.0
        await asyncio.to_thread(self._play_sound, sound_file, volume)

    @staticmethod
    def _play_sound(path: str, volume: float) -> None:
        """Blocking call to play a sound file via pygame."""
        import pygame.mixer

        pygame.mixer.init()
        sound = pygame.mixer.Sound(path)
        sound.set_volume(volume)
        channel = sound.play()
        if channel is not None:
            while channel.get_busy():
                pygame.time.wait(50)
