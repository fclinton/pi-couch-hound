"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from couch_hound.config import CONFIG_PATH, load_config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    # Startup: load config and store in app state
    config = load_config()
    app.state.config = config
    app.state.config_path = CONFIG_PATH
    yield
    # Shutdown: cleanup resources


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pi Couch Hound",
        description="Raspberry Pi-powered dog detector API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register API routes
    from couch_hound.api.routes_actions import router as actions_router
    from couch_hound.api.routes_config import router as config_router
    from couch_hound.api.routes_system import router as system_router

    app.include_router(system_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(actions_router, prefix="/api")

    # Serve frontend static files if built
    frontend_dist = Path("frontend/dist")
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True))

    return app
