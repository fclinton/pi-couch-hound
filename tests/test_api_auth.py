"""Tests for auth API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.api.auth import hash_password
from couch_hound.config import AppConfig, AuthConfig, WebConfig


@pytest.fixture
def auth_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with auth enabled and a known password."""
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


@pytest.fixture
def noauth_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with auth disabled."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(web=WebConfig(auth=AuthConfig(enabled=False)))
        yield client


# ── POST /api/auth/login ──


def test_login_success(auth_client: TestClient) -> None:
    """Successful login returns a JWT access token."""
    response = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(auth_client: TestClient) -> None:
    """Wrong password returns 401."""
    response = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrongpass"},
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_login_wrong_username(auth_client: TestClient) -> None:
    """Wrong username returns 401."""
    response = auth_client.post(
        "/api/auth/login",
        json={"username": "notadmin", "password": "testpass123"},
    )
    assert response.status_code == 401


def test_login_when_auth_disabled(noauth_client: TestClient) -> None:
    """Login when auth is disabled returns 400."""
    response = noauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]


# ── GET /api/auth/status ──


def test_auth_status_disabled(noauth_client: TestClient) -> None:
    """Auth status when auth is disabled."""
    response = noauth_client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["auth_enabled"] is False
    assert data["authenticated"] is False
    assert data["username"] is None


def test_auth_status_authenticated(auth_client: TestClient) -> None:
    """Auth status with a valid token returns authenticated."""
    # Login first to get a token
    login_resp = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]

    response = auth_client.get(
        "/api/auth/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auth_enabled"] is True
    assert data["authenticated"] is True
    assert data["username"] == "admin"


def test_auth_status_unauthenticated(auth_client: TestClient) -> None:
    """Auth status without a token returns 401 when auth is enabled."""
    response = auth_client.get("/api/auth/status")
    assert response.status_code == 401


def test_auth_status_invalid_token(auth_client: TestClient) -> None:
    """Auth status with an invalid token returns 401."""
    response = auth_client.get(
        "/api/auth/status",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


# ── POST /api/auth/change-password ──


def test_change_password_success(auth_client: TestClient) -> None:
    """Changing password with correct current password succeeds."""
    # Login first
    login_resp = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]

    # Change password
    response = auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "changed successfully" in response.json()["message"]

    # Verify new password works for login
    login_resp2 = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "newpass456"},
    )
    assert login_resp2.status_code == 200
    assert "access_token" in login_resp2.json()


def test_change_password_wrong_current(auth_client: TestClient) -> None:
    """Changing password with wrong current password fails."""
    # Login first
    login_resp = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]

    response = auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"]


def test_change_password_unauthenticated(auth_client: TestClient) -> None:
    """Changing password without a token returns 401."""
    response = auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass123", "new_password": "newpass456"},
    )
    assert response.status_code == 401


def test_change_password_auth_disabled(noauth_client: TestClient) -> None:
    """Changing password when auth is disabled returns 400."""
    response = noauth_client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass123", "new_password": "newpass456"},
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]
