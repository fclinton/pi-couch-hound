"""Shared test fixtures."""

from __future__ import annotations

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
