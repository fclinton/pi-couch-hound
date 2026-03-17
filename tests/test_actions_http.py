"""Tests for the HttpAction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from couch_hound.actions.http import HttpAction
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_http", type="http", **kwargs)


def _mock_response(status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


async def test_http_post_success() -> None:
    config = _make_config(url="https://example.com/hook", method="POST", body='{"dog": true}')
    action = HttpAction(config)

    with patch("urllib.request.urlopen", return_value=_mock_response()) as mock_open:
        await action.execute({})
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://example.com/hook"
        assert req.method == "POST"
        assert req.data == b'{"dog": true}'


async def test_http_get_no_body() -> None:
    config = _make_config(url="https://example.com/ping", method="GET")
    action = HttpAction(config)

    with patch("urllib.request.urlopen", return_value=_mock_response()) as mock_open:
        await action.execute({})
        req = mock_open.call_args[0][0]
        assert req.data is None
        assert req.method == "GET"


async def test_http_template_rendering() -> None:
    config = _make_config(
        url="https://example.com/{{label}}",
        method="POST",
        body="Detected {{label}} at {{confidence}}",
    )
    action = HttpAction(config)

    ctx = {"template_context": {"label": "dog", "confidence": "0.9500"}}
    with patch("urllib.request.urlopen", return_value=_mock_response()) as mock_open:
        await action.execute(ctx)
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://example.com/dog"
        assert req.data == b"Detected dog at 0.9500"


async def test_http_connection_error() -> None:
    config = _make_config(url="https://example.com/hook")
    action = HttpAction(config)

    with (
        patch("urllib.request.urlopen", side_effect=OSError("Connection refused")),
        pytest.raises(OSError, match="Connection refused"),
    ):
        await action.execute({})


async def test_http_default_method_is_post() -> None:
    config = _make_config(url="https://example.com/hook")
    action = HttpAction(config)

    with patch("urllib.request.urlopen", return_value=_mock_response()) as mock_open:
        await action.execute({})
        req = mock_open.call_args[0][0]
        assert req.method == "POST"


async def test_http_retries_on_transient_error() -> None:
    """HTTP action retries once on transient failure then succeeds."""
    config = _make_config(url="https://example.com/hook")
    action = HttpAction(config)

    call_count = 0
    resp = _mock_response()

    def _urlopen_side_effect(*args: object, **kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Transient failure")
        return resp

    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect):
        await action.execute({})
    assert call_count == 2


async def test_http_timeout() -> None:
    """HTTP action raises RuntimeError on timeout."""
    config = _make_config(url="https://example.com/hook")
    action = HttpAction(config)

    import couch_hound.actions.http as http_mod

    original_timeout = http_mod._REQUEST_TIMEOUT
    http_mod._REQUEST_TIMEOUT = 0.1

    def _slow_request(*args: object, **kwargs: object) -> None:
        import time

        time.sleep(1)

    try:
        with (
            patch("urllib.request.urlopen", side_effect=_slow_request),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            await action.execute({})
    finally:
        http_mod._REQUEST_TIMEOUT = original_timeout
