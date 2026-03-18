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


async def _serve_media(request: Request) -> Response:
    """Serve a local file by its path."""
    file_path = request.path_params["file_path"]
    resolved = Path(file_path)
    if not resolved.is_file():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    media_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=media_type)


async def _catch_all(request: Request) -> Response:
    """Redirect non-media requests to the main application."""
    main_port: int = request.app.state.main_port
    ssl_enabled: bool = request.app.state.ssl_enabled
    scheme = "https" if ssl_enabled else "http"
    target = f"{scheme}://{request.url.hostname}:{main_port}{request.url.path}"
    return RedirectResponse(url=target, status_code=307)


def _create_media_app(main_port: int, ssl_enabled: bool) -> Starlette:
    """Build the Starlette app used by the media server."""
    app = Starlette(
        routes=[
            Route("/media/{file_path:path}", _serve_media),
            Route("/{path:path}", _catch_all),
        ],
    )
    app.state.main_port = main_port
    app.state.ssl_enabled = ssl_enabled
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
) -> asyncio.Task[None]:
    """Start the HTTP-only media server and return the running task."""
    app = _create_media_app(main_port, ssl_enabled)
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
