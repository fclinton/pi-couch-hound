"""Detection pipeline — the core loop tying camera, detector, and actions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from couch_hound.actions import create_action
from couch_hound.actions.base import BaseAction
from couch_hound.camera import Camera
from couch_hound.config import AppConfig
from couch_hound.cooldown import CooldownManager
from couch_hound.detector import Detection, Detector
from couch_hound.roi import bbox_in_roi
from couch_hound.templates import build_context

logger = logging.getLogger(__name__)


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
        return actions

    async def start(self) -> None:
        """Open camera, load model, and start the detection loop."""
        if self._state == PipelineState.RUNNING:
            return

        try:
            self._camera = Camera(self._config.camera)
            self._detector = Detector(self._config.detection)
            self._cooldown = CooldownManager(self._config.cooldown)
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

    def update_config(self, config: AppConfig) -> None:
        """Hot-update config for next loop iteration."""
        self._config = config
        self._cooldown.update_config(config.cooldown)

    async def _run(self) -> None:
        """Main detection loop."""
        try:
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

                if detections and self._cooldown.can_trigger():
                    best = max(detections, key=lambda d: d.confidence)
                    self._cooldown.record_trigger()
                    await self._dispatch(best)
                    self._stats.detection_count += 1

                await asyncio.sleep(self._config.camera.capture_interval)
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
