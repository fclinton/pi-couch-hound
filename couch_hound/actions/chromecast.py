"""Chromecast action — casts audio to a local Chromecast device."""

from __future__ import annotations

import asyncio
import mimetypes
import socket
from typing import Any
from urllib.parse import quote

from couch_hound.actions.base import BaseAction
from couch_hound.templates import render_template

_AUDIO_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}

_DEFAULT_MEDIA_PORT = 8081


def _guess_audio_type(url: str) -> str:
    """Guess the MIME type of an audio URL."""
    mime, _ = mimetypes.guess_type(url)
    if mime and mime.startswith("audio/"):
        return mime
    for ext, audio_type in _AUDIO_TYPES.items():
        if url.lower().endswith(ext):
            return audio_type
    return "audio/mpeg"


class ChromecastAction(BaseAction):
    """Cast audio to a Chromecast device on the local network."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Discover the Chromecast and play the configured media."""
        device_name = self.config.device_name
        if not device_name:
            raise RuntimeError("No Chromecast device_name configured")

        media_url = self.config.media_url
        if not media_url and self.config.sound_file:
            media_url = self._build_local_url(self.config.sound_file)
        if not media_url:
            raise RuntimeError("No media_url or sound_file configured for chromecast action")

        media_url = render_template(media_url, context)
        volume = (self.config.volume if self.config.volume is not None else 80) / 100.0
        await asyncio.to_thread(self._cast, device_name, media_url, volume)

    @staticmethod
    def _cast(device_name: str, media_url: str, volume: float) -> None:
        """Blocking call: discover device, set volume, and play media."""
        import pychromecast

        chromecasts, browser = pychromecast.get_listed_chromecasts(
            friendly_names=[device_name],
        )
        if not chromecasts:
            raise RuntimeError(f"Chromecast '{device_name}' not found on network")
        cast = chromecasts[0]
        cast.wait()
        cast.set_volume(volume)
        mc = cast.media_controller
        content_type = _guess_audio_type(media_url)
        mc.play_media(media_url, content_type)
        mc.block_until_active()
        browser.stop_discovery()

    @staticmethod
    def _build_local_url(sound_file: str) -> str:
        """Build an HTTP URL pointing to the media server for a local file."""
        local_ip = socket.gethostbyname(socket.gethostname())
        return f"http://{local_ip}:{_DEFAULT_MEDIA_PORT}/media/{quote(sound_file, safe='/')}"
