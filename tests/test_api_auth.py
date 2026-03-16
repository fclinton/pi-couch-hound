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
    """Return a test client with auth disabled but password already set."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            web=WebConfig(
                auth=AuthConfig(
                    enabled=False,
                    password_hash=hash_password("testpass123"),
                )
            )
        )
        yield client


@pytest.fixture
def setup_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Return a test client with no password configured (fresh install)."""
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


# ── POST /api/auth/setup ──


def test_setup_success(setup_client: TestClient) -> None:
    """First-run setup creates account, enables auth, and returns JWT."""
    response = setup_client.post(
        "/api/auth/setup",
        json={"username": "myadmin", "password": "mypassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Auth should now be enabled in config
    config = setup_client.app.state.config  # type: ignore[union-attr]
    assert config.web.auth.enabled is True
    assert config.web.auth.username == "myadmin"
    assert config.web.auth.password_hash != ""


def test_setup_allows_login_after(setup_client: TestClient) -> None:
    """After setup, the configured password works for login."""
    setup_client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "setuppass"},
    )
    response = setup_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "setuppass"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_setup_rejected_when_already_configured(auth_client: TestClient) -> None:
    """Setup returns 400 when a password is already configured."""
    response = auth_client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "newpass"},
    )
    assert response.status_code == 400
    assert "already been completed" in response.json()["detail"]


# ── setup_required in GET /api/auth/status ──


def test_auth_status_setup_required(setup_client: TestClient) -> None:
    """Auth status returns setup_required=True when no password is set."""
    response = setup_client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["setup_required"] is True
    assert data["authenticated"] is False


def test_auth_status_setup_not_required(auth_client: TestClient) -> None:
    """Auth status returns setup_required=False when password is configured."""
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
    assert response.json()["setup_required"] is False
