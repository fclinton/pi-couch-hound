"""WebSocket handlers for live stream, events, and status."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import cv2
import numpy.typing as npt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from couch_hound.detector import Detection

logger = logging.getLogger(__name__)

router = APIRouter()

# JPEG encode quality for stream frames
JPEG_QUALITY = 70

# Bounding box drawing constants
BBOX_COLOR = (0, 255, 0)  # Green in BGR
BBOX_THICKNESS = 2
LABEL_FONT_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_BG_COLOR = (0, 255, 0)
LABEL_TEXT_COLOR = (0, 0, 0)


def draw_detections(frame: npt.NDArray[Any], detections: list[Detection]) -> npt.NDArray[Any]:
    """Draw bounding boxes and labels on a frame copy.

    Bboxes in Detection are normalized [0,1] as [x1, y1, x2, y2].
    """
    if not detections:
        return frame

    annotated = frame.copy()
    h, w = annotated.shape[:2]

    for det in detections:
        x1 = int(det.bbox[0] * w)
        y1 = int(det.bbox[1] * h)
        x2 = int(det.bbox[2] * w)
        y2 = int(det.bbox[3] * h)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), BBOX_COLOR, BBOX_THICKNESS)

        label = f"{det.label} {det.confidence:.2f}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, LABEL_FONT_SCALE, LABEL_THICKNESS
        )
        # Background rectangle for label
        cv2.rectangle(
            annotated,
            (x1, y1 - text_h - baseline - 4),
            (x1 + text_w, y1),
            LABEL_BG_COLOR,
            cv2.FILLED,
        )
        cv2.putText(
            annotated,
            label,
            (x1, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            LABEL_FONT_SCALE,
            LABEL_TEXT_COLOR,
            LABEL_THICKNESS,
        )

    return annotated


def encode_frame_jpeg(frame: npt.NDArray[Any], quality: int = JPEG_QUALITY) -> bytes:
    """Encode a frame as JPEG bytes."""
    success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Failed to encode frame as JPEG")
    return bytes(buffer)


class ConnectionManager:
    """Manages WebSocket connections for stream, events, and status channels."""

    def __init__(self) -> None:
        self._stream_clients: set[WebSocket] = set()
        self._event_clients: set[WebSocket] = set()
        self._status_clients: set[WebSocket] = set()

    def _get_channel(self, channel: str) -> set[WebSocket]:
        channels: dict[str, set[WebSocket]] = {
            "stream": self._stream_clients,
            "events": self._event_clients,
            "status": self._status_clients,
        }
        if channel not in channels:
            raise ValueError(f"Unknown channel: {channel}")
        return channels[channel]

    async def connect(self, ws: WebSocket, channel: str) -> None:
        """Accept and register a WebSocket connection."""
        await ws.accept()
        self._get_channel(channel).add(ws)
        count = len(self._get_channel(channel))
        logger.debug("WebSocket connected to %s (total: %d)", channel, count)

    def disconnect(self, ws: WebSocket, channel: str) -> None:
        """Remove a WebSocket connection."""
        self._get_channel(channel).discard(ws)
        logger.debug("WebSocket disconnected from %s", channel)

    @property
    def has_stream_clients(self) -> bool:
        """True if any clients are connected to the stream channel."""
        return len(self._stream_clients) > 0

    async def broadcast_frame(self, jpeg_bytes: bytes) -> None:
        """Send a JPEG frame to all stream clients."""
        disconnected: list[WebSocket] = []
        for ws in self._stream_clients:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_bytes(jpeg_bytes)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._stream_clients.discard(ws)

    async def broadcast_event(self, event: dict[str, Any]) -> None:
        """Send a detection event to all event clients."""
        disconnected: list[WebSocket] = []
        message = json.dumps(event)
        for ws in self._event_clients:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._event_clients.discard(ws)


def get_system_metrics() -> dict[str, Any]:
    """Gather system metrics from /proc and /sys (Linux only, graceful fallback)."""
    metrics: dict[str, Any] = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "temperature": None,
    }

    # CPU usage from /proc/stat (instant snapshot — simplified)
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        if parts[0] == "cpu":
            values = [int(v) for v in parts[1:]]
            idle = values[3]
            total = sum(values)
            if total > 0:
                metrics["cpu_percent"] = round((1.0 - idle / total) * 100, 1)
    except (OSError, ValueError, IndexError):
        pass

    # Memory from /proc/meminfo
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
        mem_total = meminfo.get("MemTotal", 0)
        mem_available = meminfo.get("MemAvailable", 0)
        if mem_total > 0:
            metrics["memory_percent"] = round((1.0 - mem_available / mem_total) * 100, 1)
    except (OSError, ValueError):
        pass

    # Temperature from thermal zone
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_raw = int(f.read().strip())
        metrics["temperature"] = round(temp_raw / 1000.0, 1)
    except (OSError, ValueError):
        pass

    return metrics


@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket) -> None:
    """Live MJPEG stream endpoint. Frames are pushed by the pipeline stream loop."""
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket, "stream")
    try:
        while True:
            # Keep connection alive — client may send pings or close
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "stream")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Real-time detection event push endpoint."""
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket, "events")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "events")


@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    """Periodic system status updates (CPU, mem, temp, pipeline state)."""
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket, "status")
    try:
        while True:
            pipeline = websocket.app.state.pipeline
            metrics = await asyncio.to_thread(get_system_metrics)

            status_msg: dict[str, Any] = {
                **metrics,
                "pipeline_state": str(pipeline.state),
                "detection_count": pipeline.stats.detection_count,
                "last_detection_time": pipeline.stats.last_detection_time,
            }

            await websocket.send_json(status_msg)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error in status WebSocket")
    finally:
        manager.disconnect(websocket, "status")
