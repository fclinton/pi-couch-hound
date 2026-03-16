"""Detection pipeline — the core loop tying camera, detector, and actions."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from couch_hound.actions import create_action
from couch_hound.actions.base import BaseAction
from couch_hound.camera import Camera
from couch_hound.config import AppConfig, TwoStageConfig
from couch_hound.cooldown import CooldownManager
from couch_hound.detector import Detection, Detector, SnakeDebugInfo
from couch_hound.escalation import EscalationManager
from couch_hound.roi import bbox_in_roi
from couch_hound.templates import build_context

if TYPE_CHECKING:
    from couch_hound.api.websocket import ConnectionManager
    from couch_hound.database import EventDatabase

logger = logging.getLogger(__name__)

# Stream loop target: ~15 FPS when clients are connected
_STREAM_INTERVAL = 1.0 / 15

# Auto-restart settings
_MAX_RESTART_RETRIES = 5
_BASE_BACKOFF_SECS = 2.0
_MAX_BACKOFF_SECS = 60.0
_STABLE_RUN_SECS = 60.0  # reset retry counter after running this long


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
        self._fatal_error = asyncio.Event()
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
        self._last_debug_info: SnakeDebugInfo | None = None

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    @property
    def stats(self) -> PipelineStats:
        """Runtime detection statistics."""
        return self._stats

    @property
    def fatal_error(self) -> asyncio.Event:
        """Set when the pipeline exhausts retries and cannot recover."""
        return self._fatal_error

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
        """Launch detection and stream loops, auto-restarting on failure."""
        retries = 0
        while not self._stop_event.is_set():
            loop_start = time.monotonic()
            try:
                await asyncio.gather(
                    self._detection_loop(),
                    self._stream_loop(),
                )
                break  # clean exit via stop_event
            except asyncio.CancelledError:
                raise
            except Exception:
                self._camera.close()
                self._detector.unload()

                elapsed = time.monotonic() - loop_start
                if elapsed >= _STABLE_RUN_SECS:
                    retries = 0  # was stable, reset counter

                retries += 1
                if retries > _MAX_RESTART_RETRIES:
                    self._state = PipelineState.ERROR
                    logger.exception(
                        "Pipeline crashed after %d consecutive retries, giving up",
                        _MAX_RESTART_RETRIES,
                    )
                    self._fatal_error.set()
                    return

                backoff = min(_BASE_BACKOFF_SECS * (2 ** (retries - 1)), _MAX_BACKOFF_SECS)
                logger.exception(
                    "Pipeline error (retry %d/%d), restarting in %.1fs",
                    retries,
                    _MAX_RESTART_RETRIES,
                    backoff,
                )

                # Wait for backoff, but exit early if stop is requested
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                    break  # stop requested during backoff
                except TimeoutError:
                    pass

                # Re-initialise camera and detector for the retry
                try:
                    self._camera = Camera(self._config.camera)
                    self._detector = Detector(self._config.detection)
                    await asyncio.to_thread(self._camera.open)
                    await asyncio.to_thread(self._detector.load)
                except Exception:
                    logger.exception("Failed to re-initialise for retry")
                    continue  # counts as another retry on next iteration
        else:
            # Exited while-loop because stop_event was already set
            self._camera.close()
            self._detector.unload()

        self._camera.close()
        self._detector.unload()
        if self._state != PipelineState.ERROR:
            self._state = PipelineState.STOPPED

    async def _two_stage_detect(
        self,
        frame: npt.NDArray[Any],
        two_stage_cfg: TwoStageConfig,
    ) -> list[Detection]:
        """Two-stage detection: find anchor, then snake contours for hi-res crops.

        Stage 1: Run scene-wide detection to locate the anchor object (e.g. couch).
        Stage 2: Use active-contour edge detection (snakes) to outline objects
                 within the anchor region, then run the model on a tight 300x300
                 crop around each contour. This gives full model resolution per
                 object — even on a wide couch — with no wasted inference on
                 empty cushion space.
        """
        # Stage 1: Find anchor objects at a lower threshold
        scene_detections = await asyncio.to_thread(
            self._detector.detect_with_threshold,
            frame,
            two_stage_cfg.anchor_confidence,
        )

        anchors = [d for d in scene_detections if d.label == two_stage_cfg.anchor_label]

        if not anchors:
            # No anchor found — fall back to normal single-stage detection
            self._last_debug_info = None
            return await asyncio.to_thread(self._detector.detect, frame)

        # Stage 2: Snake each anchor region
        all_detections: list[Detection] = list(scene_detections)
        last_debug: SnakeDebugInfo | None = None

        for anchor in anchors:
            snake_detections, debug_info = await asyncio.to_thread(
                self._detector.snake_detect,
                frame,
                anchor.bbox,
                two_stage_cfg.anchor_padding,
                two_stage_cfg.second_stage_confidence,
                two_stage_cfg.min_contour_area,
                two_stage_cfg.contour_padding,
            )
            last_debug = debug_info
            for det in snake_detections:
                # Skip re-detecting the anchor itself
                if det.label == two_stage_cfg.anchor_label:
                    continue
                all_detections.append(det)

        # Cache debug info for the stream overlay
        self._last_debug_info = last_debug if two_stage_cfg.debug_overlay else None

        logger.debug(
            "Two-stage snake: %d anchor(s), %d total detections",
            len(anchors),
            len(all_detections),
        )
        return all_detections

    async def _detection_loop(self) -> None:
        """Core detection loop: grab frame, detect, filter, dispatch."""
        while not self._stop_event.is_set():
            frame = await asyncio.to_thread(self._camera.grab_frame)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            two_stage = self._config.detection.two_stage
            if two_stage.enabled:
                detections = await self._two_stage_detect(frame, two_stage)
            else:
                self._last_debug_info = None
                detections = await asyncio.to_thread(self._detector.detect, frame)

            # Update cached detections for the stream overlay (all classes)
            self._last_detections = detections

            # Filter to target detections only for action dispatch
            target_detections = [d for d in detections if d.is_target]
            if self._config.detection.roi.enabled:
                target_detections = [
                    d
                    for d in target_detections
                    if bbox_in_roi(
                        d.bbox,
                        self._config.detection.roi.polygon,
                        self._config.detection.roi.min_overlap,
                    )
                ]

            if self._config.escalation.enabled:
                await self._escalation_dispatch(target_detections)
            else:
                if target_detections and self._cooldown.can_trigger():
                    best = max(target_detections, key=lambda d: d.confidence)
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
        from couch_hound.api.websocket import (
            draw_debug_overlay,
            draw_detections,
            encode_frame_jpeg,
        )

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
            if self._last_debug_info is not None:
                annotated = draw_debug_overlay(annotated, self._last_debug_info)
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
