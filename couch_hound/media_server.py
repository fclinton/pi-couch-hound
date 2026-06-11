"""Lightweight HTTP-only media server for serving files to Chromecast devices.

Chromecast devices cannot verify self-signed TLS certificates, so this server
runs on a separate port using plain HTTP.  Only the ``/media/`` path is served;
all other requests are redirected to the main application port.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

logger = logging.getLogger(__name__)


# Only audio files are ever served to Chromecast devices; restricting the
# extension set keeps this unauthenticated port from being a general file reader.
_ALLOWED_MEDIA_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aac"}


async def _serve_media(request: Request) -> Response:
    """Serve a local audio file confined to the configured media root."""
    media_root: Path = request.app.state.media_root
    file_path = request.path_params["file_path"]

    # Resolve the request against the media root and confirm it does not escape
    # it (rejects absolute paths and ../ traversal). resolve() collapses '..'.
    candidate = (media_root / file_path).resolve()
    if not candidate.is_relative_to(media_root):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if candidate.suffix.lower() not in _ALLOWED_MEDIA_EXTENSIONS:
        return JSONResponse({"detail": "Unsupported media type"}, status_code=415)
    if not candidate.is_file():
        return JSONResponse({"detail": "Not found"}, status_code=404)

    media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    return FileResponse(candidate, media_type=media_type)


async def _catch_all(request: Request) -> Response:
    """Redirect non-media requests to the main application."""
    main_port: int = request.app.state.main_port
    ssl_enabled: bool = request.app.state.ssl_enabled
    scheme = "https" if ssl_enabled else "http"
    target = f"{scheme}://{request.url.hostname}:{main_port}{request.url.path}"
    return RedirectResponse(url=target, status_code=307)


def _create_media_app(
    main_port: int, ssl_enabled: bool, media_root: Path | None = None
) -> Starlette:
    """Build the Starlette app used by the media server."""
    app = Starlette(
        routes=[
            Route("/media/{file_path:path}", _serve_media),
            Route("/{path:path}", _catch_all),
        ],
    )
    app.state.main_port = main_port
    app.state.ssl_enabled = ssl_enabled
    app.state.media_root = (media_root or Path.cwd()).resolve()
    return app


async def _run_server(server: uvicorn.Server, port: int) -> None:
    """Run the uvicorn server, catching bind failures gracefully."""
    try:
        await server.serve()
    except SystemExit:
        logger.warning("Media server failed to start on port %d (address in use?)", port)


async def start_media_server(
    media_port: int,
    main_port: int,
    ssl_enabled: bool,
    media_root: Path | None = None,
) -> asyncio.Task[None]:
    """Start the HTTP-only media server and return the running task."""
    app = _create_media_app(main_port, ssl_enabled, media_root)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=media_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task: asyncio.Task[None] = asyncio.create_task(_run_server(server, media_port))
    logger.info("Media server starting on port %d (HTTP only)", media_port)
    return task
