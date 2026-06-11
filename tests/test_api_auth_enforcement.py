"""Tests that authentication is enforced across protected API routes.

These guard against the regression where ``require_auth`` was wired into only a
couple of endpoints, leaving the rest of the API unauthenticated.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.api.auth import create_access_token, hash_password
from couch_hound.config import AppConfig, AuthConfig, WebConfig

# A representative sample of protected endpoints across the routers.
PROTECTED_GET_ROUTES = [
    "/api/status",
    "/api/config",
    "/api/events",
    "/api/snapshots/example.jpg",
    "/api/sounds",
    "/api/models",
    "/api/logs",
]

# Endpoints that must remain reachable without authentication.
PUBLIC_ROUTES = [
    "/api/health",
    "/api/auth/status",
]


@pytest.fixture
def auth_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Test client with auth enabled and a known password."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            web=WebConfig(
                auth=AuthConfig(
                    enabled=True,
                    username="admin",
                    password_hash=hash_password("testpass123"),
                )
            )
        )
        yield client


@pytest.mark.parametrize("route", PROTECTED_GET_ROUTES)
def test_protected_route_requires_auth(auth_client: TestClient, route: str) -> None:
    """Without a token, protected routes return 401 when auth is enabled."""
    response = auth_client.get(route)
    assert response.status_code == 401, f"{route} should require auth"


@pytest.mark.parametrize("route", PROTECTED_GET_ROUTES)
def test_protected_route_rejects_invalid_token(auth_client: TestClient, route: str) -> None:
    """A forged/invalid token is rejected on protected routes."""
    response = auth_client.get(route, headers={"Authorization": "Bearer not.a.real.token"})
    assert response.status_code == 401, f"{route} should reject invalid tokens"


@pytest.mark.parametrize("route", PROTECTED_GET_ROUTES)
def test_protected_route_accepts_valid_token(auth_client: TestClient, route: str) -> None:
    """With a valid token, protected routes are reachable (not 401)."""
    token = create_access_token("admin")
    response = auth_client.get(route, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401, f"{route} should accept a valid token"


@pytest.mark.parametrize("route", PUBLIC_ROUTES)
def test_public_route_no_auth_required(auth_client: TestClient, route: str) -> None:
    """Health and auth-status stay reachable without a token."""
    response = auth_client.get(route)
    assert response.status_code == 200, f"{route} should be public"


def test_mutating_route_requires_auth(auth_client: TestClient) -> None:
    """A representative POST (test-actions) is also protected."""
    response = auth_client.post("/api/test-actions")
    assert response.status_code == 401


def test_routes_open_when_auth_disabled() -> None:
    """With auth disabled (default), protected routes do not 401."""
    app = create_app()
    with TestClient(app) as client:
        # Default AppConfig has auth disabled.
        response = client.get("/api/status")
        assert response.status_code != 401
