"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from couch_hound.api.websocket import ConnectionManager
from couch_hound.config import CONFIG_PATH, AppConfig, load_config
from couch_hound.database import EventDatabase
from couch_hound.pipeline import DetectionPipeline
from couch_hound.updater import UpdateManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    # Startup: load config and store in app state
    try:
        config = load_config()
    except Exception:
        logger.exception("Config load failed, starting with defaults")
        config = AppConfig()
    app.state.config = config
    app.state.config_path = CONFIG_PATH

    # Create WebSocket connection manager
    ws_manager = ConnectionManager()
    app.state.ws_manager = ws_manager

    # Initialize event database
    event_db: EventDatabase | None = None
    try:
        event_db = EventDatabase()
        await event_db.init()
    except Exception:
        logger.exception("Event database initialization failed, events will be unavailable")
        event_db = None
    app.state.event_db = event_db

    # Start detection pipeline with WebSocket broadcasting and event logging
    pipeline = DetectionPipeline(config)
    pipeline.set_connection_manager(ws_manager)
    if event_db is not None:
        pipeline.set_event_db(event_db)
    app.state.pipeline = pipeline
    await pipeline.start()

    # Start update manager
    update_manager = UpdateManager(config.update)
    app.state.update_manager = update_manager
    update_stop = asyncio.Event()
    update_task = await update_manager.start(update_stop)

    # Watchdog: if pipeline permanently fails, terminate so systemd can restart us
    async def _pipeline_watchdog() -> None:
        await pipeline.fatal_error.wait()
        logger.critical("Pipeline fatal error — shutting down process for restart")
        os.kill(os.getpid(), signal.SIGTERM)

    watchdog_task = asyncio.create_task(_pipeline_watchdog())

    yield

    watchdog_task.cancel()

    # Shutdown: stop update checker, pipeline, and database
    update_stop.set()
    if update_task is not None:
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass
    await pipeline.stop()
    if event_db is not None:
        await event_db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pi Couch Hound",
        description="Raspberry Pi-powered dog detector API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Register API routes
    from couch_hound.api.routes_actions import router as actions_router
    from couch_hound.api.routes_auth import router as auth_router
    from couch_hound.api.routes_config import router as config_router
    from couch_hound.api.routes_events import router as events_router
    from couch_hound.api.routes_logs import router as logs_router
    from couch_hound.api.routes_roi import router as roi_router
    from couch_hound.api.routes_snapshots import router as snapshots_router
    from couch_hound.api.routes_system import router as system_router
    from couch_hound.api.routes_update import router as update_router
    from couch_hound.api.routes_upload import router as upload_router
    from couch_hound.api.websocket import router as ws_router

    app.include_router(system_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(actions_router, prefix="/api")
    app.include_router(update_router, prefix="/api")
    app.include_router(upload_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")
    app.include_router(roi_router, prefix="/api")
    app.include_router(snapshots_router, prefix="/api")
    app.include_router(ws_router)

    # Serve frontend static files with SPA fallback if built
    frontend_dist = Path("frontend/dist")
    if frontend_dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True))

    return app


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to index.html for SPA routing."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except Exception:
            # If the file is not found, serve index.html for client-side routing
            index = Path(self.directory) / "index.html"  # type: ignore[arg-type]
            if index.is_file():
                response = FileResponse(index)
                await response(scope, receive, send)
            else:
                raise
