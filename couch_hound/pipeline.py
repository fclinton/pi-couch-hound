"""Detection pipeline — the core loop tying camera, detector, and actions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from couch_hound.actions import create_action
from couch_hound.actions.base import BaseAction
from couch_hound.camera import Camera
from couch_hound.config import AppConfig
from couch_hound.cooldown import CooldownManager
from couch_hound.detector import Detection, Detector
from couch_hound.escalation import EscalationManager
from couch_hound.roi import bbox_in_roi
from couch_hound.templates import build_context

if TYPE_CHECKING:
    from couch_hound.api.websocket import ConnectionManager
    from couch_hound.database import EventDatabase

logger = logging.getLogger(__name__)

# Stream loop target: ~15 FPS when clients are connected
_STREAM_INTERVAL = 1.0 / 15


class PipelineState(StrEnum):
    """Pipeline lifecycle states."""

    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class PipelineStats:
    """Runtime statistics for the detection pipeline."""

    detection_count: int = 0
    last_detection_time: str | None = None


class DetectionPipeline:
    """Async detection loop: grab frames, detect, cooldown, dispatch actions."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._state = PipelineState.STOPPED
        self._stats = PipelineStats()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._camera = Camera(config.camera)
        self._detector = Detector(config.detection)
        self._cooldown = CooldownManager(config.cooldown)
        self._actions: list[BaseAction] = []
        self._actions_by_name: dict[str, BaseAction] = {}
        self._escalation = EscalationManager(config.escalation)
        self._connection_manager: ConnectionManager | None = None
        self._event_db: EventDatabase | None = None
        self._last_detections: list[Detection] = []

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    @property
    def stats(self) -> PipelineStats:
        """Runtime detection statistics."""
        return self._stats

    def _build_actions(self) -> list[BaseAction]:
        """Instantiate action handlers from config."""
        actions: list[BaseAction] = []
        for action_cfg in self._config.actions:
            if not action_cfg.enabled:
                continue
            try:
                actions.append(create_action(action_cfg))
            except NotImplementedError:
                logger.warning("Skipping unregistered action type: %s", action_cfg.type)
        self._actions_by_name = {a.name: a for a in actions}
        return actions

    async def start(self) -> None:
        """Open camera, load model, and start the detection loop."""
        if self._state == PipelineState.RUNNING:
            return

        try:
            self._camera = Camera(self._config.camera)
            self._detector = Detector(self._config.detection)
            self._cooldown = CooldownManager(self._config.cooldown)
            self._escalation = EscalationManager(self._config.escalation)
            self._actions = self._build_actions()

            await asyncio.to_thread(self._camera.open)
            await asyncio.to_thread(self._detector.load)
        except Exception:
            self._state = PipelineState.ERROR
            logger.exception("Failed to start detection pipeline")
            return

        self._stop_event.clear()
        self._state = PipelineState.RUNNING
        self._task = asyncio.create_task(self._run())
        logger.info("Detection pipeline started")

    async def stop(self) -> None:
        """Signal the detection loop to stop and wait for cleanup."""
        if self._task is None:
            return

        self._stop_event.set()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Detection pipeline stopped")

    async def restart(self) -> None:
        """Stop and re-start the pipeline (picks up new config)."""
        await self.stop()
        await self.start()

    def set_connection_manager(self, manager: ConnectionManager) -> None:
        """Attach a ConnectionManager for WebSocket broadcasting."""
        self._connection_manager = manager

    def set_event_db(self, db: EventDatabase) -> None:
        """Attach an EventDatabase for persisting detection events."""
        self._event_db = db

    def update_config(self, config: AppConfig) -> None:
        """Hot-update config for next loop iteration."""
        self._config = config
        self._cooldown.update_config(config.cooldown)
        self._escalation.update_config(config.escalation)

    async def _run(self) -> None:
        """Launch detection and stream loops concurrently."""
        try:
            await asyncio.gather(
                self._detection_loop(),
                self._stream_loop(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._state = PipelineState.ERROR
            logger.exception("Detection pipeline error")
        finally:
            self._camera.close()
            self._detector.unload()
            if self._state != PipelineState.ERROR:
                self._state = PipelineState.STOPPED

    async def _detection_loop(self) -> None:
        """Core detection loop: grab frame, detect, filter, dispatch."""
        while not self._stop_event.is_set():
            frame = await asyncio.to_thread(self._camera.grab_frame)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            detections = await asyncio.to_thread(self._detector.detect, frame)

            if self._config.detection.roi.enabled:
                detections = [
                    d
                    for d in detections
                    if bbox_in_roi(
                        d.bbox,
                        self._config.detection.roi.polygon,
                        self._config.detection.roi.min_overlap,
                    )
                ]

            # Update cached detections for the stream overlay
            self._last_detections = detections

            if self._config.escalation.enabled:
                await self._escalation_dispatch(detections)
            else:
                if detections and self._cooldown.can_trigger():
                    best = max(detections, key=lambda d: d.confidence)
                    self._cooldown.record_trigger()
                    await self._dispatch(best)
                    self._stats.detection_count += 1

            await asyncio.sleep(self._config.camera.capture_interval)

    async def _escalation_dispatch(self, detections: list[Detection]) -> None:
        """Drive the escalation manager and dispatch level-specific actions."""
        detected = bool(detections)
        levels_to_fire = self._escalation.update_detection(detected)

        if not levels_to_fire or not detections:
            return

        best = max(detections, key=lambda d: d.confidence)
        timestamp = datetime.now(tz=UTC).isoformat()

        for level_idx in levels_to_fire:
            if level_idx >= len(self._config.escalation.levels):
                continue
            level_cfg = self._config.escalation.levels[level_idx]
            esc_vars = self._escalation.get_context_vars(level_idx)

            context = build_context(
                label=best.label,
                confidence=best.confidence,
                bbox=best.bbox,
                timestamp=timestamp,
                escalation_level=esc_vars["escalation_level"],
                escalation_elapsed=esc_vars["escalation_elapsed"],
            )
            self._stats.last_detection_time = timestamp

            for action_name in level_cfg.actions:
                action = self._actions_by_name.get(action_name)
                if action is None:
                    logger.warning(
                        "Escalation level %d references unknown action: %s",
                        level_idx + 1,
                        action_name,
                    )
                    continue
                try:
                    await action.execute(context)
                except Exception:
                    logger.exception(
                        "Action '%s' failed (escalation level %d)", action_name, level_idx + 1
                    )

        self._stats.detection_count += 1

        # Broadcast event to WebSocket clients
        if self._connection_manager is not None:
            event_data = {
                "timestamp": timestamp,
                "label": best.label,
                "confidence": best.confidence,
                "bbox": best.bbox,
            }
            await self._connection_manager.broadcast_event(event_data)

        # Persist event to database
        if self._event_db is not None:
            try:
                fired_actions: list[str] = []
                for level_idx in levels_to_fire:
                    if level_idx < len(self._config.escalation.levels):
                        fired_actions.extend(self._config.escalation.levels[level_idx].actions)
                await self._event_db.insert_event(
                    timestamp=timestamp,
                    confidence=best.confidence,
                    label=best.label,
                    bbox=best.bbox,
                    snapshot_path=None,
                    actions_fired=fired_actions,
                )
            except Exception:
                logger.exception("Failed to persist detection event to database")

    async def _stream_loop(self) -> None:
        """Fast frame-grab loop for live streaming with cached detection overlays."""
        from couch_hound.api.websocket import draw_detections, encode_frame_jpeg

        while not self._stop_event.is_set():
            mgr = self._connection_manager
            if mgr is None or not mgr.has_stream_clients:
                await asyncio.sleep(0.5)
                continue

            frame = await asyncio.to_thread(self._camera.grab_frame)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            annotated = draw_detections(frame, self._last_detections)
            jpeg_bytes = await asyncio.to_thread(encode_frame_jpeg, annotated)
            await mgr.broadcast_frame(jpeg_bytes)

            await asyncio.sleep(_STREAM_INTERVAL)

    async def _dispatch(self, detection: Detection) -> None:
        """Build context and fire all enabled actions."""
        timestamp = datetime.now(tz=UTC).isoformat()
        context = build_context(
            label=detection.label,
            confidence=detection.confidence,
            bbox=detection.bbox,
            timestamp=timestamp,
        )
        self._stats.last_detection_time = timestamp

        for action in self._actions:
            try:
                await action.execute(context)
            except Exception:
                logger.exception("Action '%s' failed", action.name)

        # Broadcast event to WebSocket clients
        if self._connection_manager is not None:
            event_data = {
                "timestamp": timestamp,
                "label": detection.label,
                "confidence": detection.confidence,
                "bbox": detection.bbox,
            }
            await self._connection_manager.broadcast_event(event_data)

        # Persist event to database
        if self._event_db is not None:
            try:
                action_names = [a.name for a in self._actions]
                snapshot_path = context.get("snapshot_path")
                await self._event_db.insert_event(
                    timestamp=timestamp,
                    confidence=detection.confidence,
                    label=detection.label,
                    bbox=detection.bbox,
                    snapshot_path=str(snapshot_path) if snapshot_path else None,
                    actions_fired=action_names,
                )
            except Exception:
                logger.exception("Failed to persist detection event to database")
