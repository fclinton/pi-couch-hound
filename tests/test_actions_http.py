"""Tests for the HttpAction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from couch_hound.actions.http import HttpAction
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_http", type="http", **kwargs)


async def test_http_post_success() -> None:
    config = _make_config(url="https://example.com/hook", method="POST", body='{"dog": true}')
    action = HttpAction(config)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        await action.execute({})
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://example.com/hook"
        assert req.method == "POST"
        assert req.data == b'{"dog": true}'


async def test_http_get_no_body() -> None:
    config = _make_config(url="https://example.com/ping", method="GET")
    action = HttpAction(config)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
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

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    ctx = {"template_context": {"label": "dog", "confidence": "0.9500"}}
    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
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

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        await action.execute({})
        req = mock_open.call_args[0][0]
        assert req.method == "POST"
