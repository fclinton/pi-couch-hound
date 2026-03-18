"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import AppConfig


@pytest.fixture
def app_config() -> AppConfig:
    """Return a default test configuration."""
    return AppConfig()


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def config_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with a writable config file."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        yield client
