"""JWT authentication middleware and helpers."""

from __future__ import annotations

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError

logger = logging.getLogger(__name__)

# JWT settings
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours

# The signing secret is loaded from the COUCH_HOUND_JWT_SECRET environment
# variable if set, otherwise generated once and persisted to this file. It is
# never a hardcoded constant — a shared default would let anyone forge tokens.
SECRET_ENV_VAR = "COUCH_HOUND_JWT_SECRET"
SECRET_PATH = Path("data/jwt_secret")

_cached_secret: str | None = None

_bearer_scheme = HTTPBearer(auto_error=False)


def _get_secret() -> str:
    """Return the JWT signing secret, loading or generating it on first use.

    Resolution order: cached value, then ``COUCH_HOUND_JWT_SECRET``, then the
    persisted secret file, otherwise a freshly generated secret persisted to
    that file (falling back to a process-lifetime secret if it cannot be saved).
    """
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret

    env_secret = os.environ.get(SECRET_ENV_VAR)
    if env_secret:
        _cached_secret = env_secret
        return _cached_secret

    try:
        if SECRET_PATH.exists():
            existing = SECRET_PATH.read_text().strip()
            if existing:
                _cached_secret = existing
                return _cached_secret
        secret = secrets.token_urlsafe(48)
        SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECRET_PATH.write_text(secret)
        os.chmod(SECRET_PATH, 0o600)
        logger.info("Generated new JWT signing secret at %s", SECRET_PATH)
        _cached_secret = secret
    except OSError:
        logger.warning(
            "Could not persist JWT secret to %s; using an ephemeral per-process secret "
            "(tokens will not survive a restart)",
            SECRET_PATH,
        )
        _cached_secret = secrets.token_urlsafe(48)
    return _cached_secret


def init_jwt_secret() -> None:
    """Eagerly load or generate the signing secret (called at startup)."""
    _get_secret()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def create_access_token(username: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    payload: dict[str, Any] = {"sub": username, "exp": expire}
    token: str = jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    return jwt.decode(
        token,
        _get_secret(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    """Dependency that enforces authentication when auth is enabled.

    Returns the username if auth is enabled and valid, or None if auth is disabled.
    Raises 401 if auth is enabled but credentials are missing/invalid.
    """
    config = request.app.state.config
    if not config.web.auth.enabled or not config.web.auth.password_hash:
        return None

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def optional_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    """Soft auth: return the username for a valid token, otherwise None.

    Never raises. Used by endpoints (e.g. auth status) that must remain
    reachable without credentials so the client can discover login is required.
    """
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except PyJWTError:
        return None
    username: str | None = payload.get("sub")
    return username


def is_token_valid(config: Any, token: str | None) -> bool:
    """Return whether a request is authorized given the app config and a token.

    Used for WebSocket endpoints, where the bearer scheme cannot be applied and
    the token arrives as a query parameter. Returns True when auth is disabled.
    """
    if not config.web.auth.enabled or not config.web.auth.password_hash:
        return True
    if not token:
        return False
    try:
        payload = decode_access_token(token)
    except PyJWTError:
        return False
    return payload.get("sub") is not None
