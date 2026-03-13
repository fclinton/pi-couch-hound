"""Tests for WebSocket endpoints, ConnectionManager, and frame helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from couch_hound.api.websocket import (
    ConnectionManager,
    draw_detections,
    encode_frame_jpeg,
)
from couch_hound.api.websocket import (
    router as ws_router,
)
from couch_hound.detector import Detection
from couch_hound.pipeline import PipelineState, PipelineStats


@pytest.fixture
def ws_app() -> FastAPI:
    """Create a minimal FastAPI app with WebSocket routes and mock state."""
    app = FastAPI()
    app.include_router(ws_router)

    # Set up mock app state matching what lifespan provides
    app.state.ws_manager = ConnectionManager()

    # Mock pipeline with just the attributes WS endpoints need
    mock_pipeline = MagicMock()
    mock_pipeline.state = PipelineState.RUNNING
    mock_pipeline.stats = PipelineStats(detection_count=3, last_detection_time=None)
    app.state.pipeline = mock_pipeline

    return app


@pytest.fixture
def ws_client(ws_app: FastAPI) -> TestClient:
    """TestClient for WebSocket endpoint tests."""
    return TestClient(ws_app)


# ---------------------------------------------------------------------------
# Helper: draw_detections
# ---------------------------------------------------------------------------


class TestDrawDetections:
    def test_empty_detections_returns_same_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = draw_detections(frame, [])
        assert result is frame  # no copy when empty

    def test_draws_bounding_box(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [Detection(label="dog", confidence=0.92, bbox=[0.1, 0.2, 0.5, 0.8])]
        result = draw_detections(frame, detections)
        # Result should be a different array (copy)
        assert result is not frame
        # The annotated frame should have non-zero pixels (drawn bbox)
        assert result.sum() > 0

    def test_does_not_mutate_original(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        detections = [Detection(label="dog", confidence=0.75, bbox=[0.0, 0.0, 1.0, 1.0])]
        draw_detections(frame, detections)
        assert frame.sum() == 0  # original unchanged


# ---------------------------------------------------------------------------
# Helper: encode_frame_jpeg
# ---------------------------------------------------------------------------


class TestEncodeFrameJpeg:
    def test_returns_valid_jpeg(self):
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        jpeg_bytes = encode_frame_jpeg(frame)
        # JPEG magic bytes
        assert jpeg_bytes[:2] == b"\xff\xd8"
        assert jpeg_bytes[-2:] == b"\xff\xd9"

    def test_custom_quality(self):
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        low_q = encode_frame_jpeg(frame, quality=10)
        high_q = encode_frame_jpeg(frame, quality=95)
        # Higher quality should produce larger output
        assert len(high_q) > len(low_q)


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------


class TestConnectionManager:
    @pytest.fixture
    def manager(self) -> ConnectionManager:
        return ConnectionManager()

    def _make_ws(self, connected: bool = True) -> MagicMock:
        """Create a mock WebSocket."""
        from starlette.websockets import WebSocketState

        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
        return ws

    async def test_connect_and_disconnect(self, manager: ConnectionManager):
        ws = self._make_ws()
        await manager.connect(ws, "stream")
        assert manager.has_stream_clients
        manager.disconnect(ws, "stream")
        assert not manager.has_stream_clients

    async def test_has_stream_clients_false_when_empty(self, manager: ConnectionManager):
        assert not manager.has_stream_clients

    async def test_broadcast_frame(self, manager: ConnectionManager):
        ws = self._make_ws()
        await manager.connect(ws, "stream")
        await manager.broadcast_frame(b"\xff\xd8test\xff\xd9")
        ws.send_bytes.assert_awaited_once_with(b"\xff\xd8test\xff\xd9")

    async def test_broadcast_frame_removes_disconnected(self, manager: ConnectionManager):
        ws = self._make_ws()
        await manager.connect(ws, "stream")
        ws.send_bytes.side_effect = RuntimeError("disconnected")
        await manager.broadcast_frame(b"data")
        # Should have been removed
        assert not manager.has_stream_clients

    async def test_broadcast_event(self, manager: ConnectionManager):
        ws = self._make_ws()
        await manager.connect(ws, "events")
        event = {"timestamp": "2026-01-01T00:00:00", "label": "dog", "confidence": 0.9}
        await manager.broadcast_event(event)
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["label"] == "dog"

    async def test_broadcast_event_removes_disconnected(self, manager: ConnectionManager):
        ws = self._make_ws()
        await manager.connect(ws, "events")
        ws.send_text.side_effect = RuntimeError("gone")
        await manager.broadcast_event({"test": True})
        # Event clients should be empty now
        assert len(manager._event_clients) == 0

    async def test_invalid_channel_raises(self, manager: ConnectionManager):
        ws = self._make_ws()
        with pytest.raises(ValueError, match="Unknown channel"):
            await manager.connect(ws, "invalid")


# ---------------------------------------------------------------------------
# WebSocket endpoints (integration via TestClient)
# ---------------------------------------------------------------------------


class TestWsStream:
    def test_stream_connect_disconnect(self, ws_client: TestClient):
        with ws_client.websocket_connect("/ws/stream") as ws:
            assert ws is not None


class TestWsEvents:
    def test_events_connect_disconnect(self, ws_client: TestClient):
        with ws_client.websocket_connect("/ws/events") as ws:
            assert ws is not None


class TestWsStatus:
    def test_status_receives_json(self, ws_client: TestClient):
        with patch(
            "couch_hound.api.websocket.get_system_metrics",
            return_value={
                "cpu_percent": 25.0,
                "memory_percent": 50.0,
                "temperature": 45.0,
            },
        ):
            with ws_client.websocket_connect("/ws/status") as ws:
                data = ws.receive_json()
                assert "cpu_percent" in data
                assert "memory_percent" in data
                assert "pipeline_state" in data
                assert "detection_count" in data

    def test_status_has_pipeline_info(self, ws_client: TestClient):
        with patch(
            "couch_hound.api.websocket.get_system_metrics",
            return_value={
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "temperature": None,
            },
        ):
            with ws_client.websocket_connect("/ws/status") as ws:
                data = ws.receive_json()
                assert data["pipeline_state"] in ("running", "stopped", "error")
                assert isinstance(data["detection_count"], int)
