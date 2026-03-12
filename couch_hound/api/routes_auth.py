"""Authentication endpoints: login, change password, auth status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from couch_hound.api.auth import (
    create_access_token,
    hash_password,
    require_auth,
    verify_password,
)
from couch_hound.api.schemas import (
    AuthStatusResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
)
from couch_hound.config import AppConfig, save_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    """Authenticate with username and password, returns a JWT."""
    config: AppConfig = request.app.state.config
    auth_cfg = config.web.auth

    if not auth_cfg.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not enabled",
        )

    if body.username != auth_cfg.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not auth_cfg.password_hash or not verify_password(body.password, auth_cfg.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(body.username)
    return LoginResponse(access_token=token)


@router.post("/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    username: str | None = Depends(require_auth),
) -> ChangePasswordResponse:
    """Update the password. Requires the current password for verification."""
    config: AppConfig = request.app.state.config
    auth_cfg = config.web.auth

    if not auth_cfg.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not enabled",
        )

    if not auth_cfg.password_hash or not verify_password(
        body.current_password, auth_cfg.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    config.web.auth.password_hash = hash_password(body.new_password)
    save_config(config, request.app.state.config_path)

    logger.info("Password changed for user '%s'", auth_cfg.username)
    return ChangePasswordResponse(message="Password changed successfully")


@router.get("/status")
async def auth_status(
    request: Request,
    username: str | None = Depends(require_auth),
) -> AuthStatusResponse:
    """Check whether auth is enabled and if the current session is valid."""
    config: AppConfig = request.app.state.config
    auth_enabled = config.web.auth.enabled

    if not auth_enabled:
        return AuthStatusResponse(auth_enabled=False, authenticated=False)

    return AuthStatusResponse(
        auth_enabled=True,
        authenticated=username is not None,
        username=username,
    )
