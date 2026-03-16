"""Update check and apply endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from couch_hound.api.schemas import UpdateStatusResponse
from couch_hound.updater import UpdateManager, UpdateState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["update"])


def _manager(request: Request) -> UpdateManager:
    return request.app.state.update_manager  # type: ignore[no-any-return]


def _to_response(manager: UpdateManager) -> UpdateStatusResponse:
    info = manager.get_info()
    return UpdateStatusResponse(
        state=info.state.value,
        current_commit=info.current_commit,
        remote_commit=info.remote_commit,
        current_version=info.current_version,
        available_version=info.available_version,
        last_check_time=info.last_check_time,
        last_error=info.last_error,
        commits_behind=info.commits_behind,
        commit_messages=info.commit_messages,
    )


@router.get("/update/status")
async def get_update_status(request: Request) -> UpdateStatusResponse:
    """Return the current update state."""
    return _to_response(_manager(request))


@router.post("/update/check")
async def check_for_updates(request: Request) -> UpdateStatusResponse:
    """Trigger a manual update check."""
    mgr = _manager(request)
    await mgr.check_for_updates()
    return _to_response(mgr)


@router.post("/update/apply")
async def apply_update(request: Request) -> UpdateStatusResponse:
    """Apply an available update. Returns 409 if no update is available."""
    mgr = _manager(request)
    info = mgr.get_info()

    if info.state == UpdateState.APPLYING:
        raise HTTPException(status_code=409, detail="Update already in progress")
    if info.state != UpdateState.AVAILABLE:
        raise HTTPException(status_code=409, detail="No update available to apply")

    await mgr.apply_update()
    return _to_response(mgr)
