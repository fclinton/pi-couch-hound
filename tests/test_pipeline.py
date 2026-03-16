"""Tests for the detection pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from couch_hound.config import (
    AppConfig,
    CooldownConfig,
    DetectionConfig,
    RoiConfig,
    TwoStageConfig,
)
from couch_hound.detector import Detection
from couch_hound.pipeline import DetectionPipeline, PipelineState


def _make_mock_camera(stop_after: int = 1, pipeline: DetectionPipeline | None = None) -> MagicMock:
    """Create a mock camera that returns frames then signals stop."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cam = MagicMock()
    cam.open = MagicMock()
    cam.close = MagicMock()
    call_count = 0

    def grab(
        *,
        _frame: object = frame,
        _stop: int = stop_after,
        _pipe: DetectionPipeline | None = pipeline,
    ) -> object:
        nonlocal call_count
        call_count += 1
        if call_count > _stop:
            if _pipe is not None:
                _pipe._stop_event.set()
            return None
        return _frame

    cam.grab_frame = MagicMock(side_effect=grab)
    return cam


def _make_mock_detector(
    detections: list[Detection] | None = None,
) -> MagicMock:
    """Create a mock detector returning canned detections."""
    det = MagicMock()
    det.load = MagicMock()
    det.unload = MagicMock()
    if detections is None:
        detections = [
            Detection(label="dog", confidence=0.92, bbox=[0.1, 0.2, 0.5, 0.6], is_target=True)
        ]
    det.detect = MagicMock(return_value=detections)
    return det


class TestPipelineStartStop:
    async def test_start_and_stop(self) -> None:
        config = AppConfig()
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera()
        mock_det = _make_mock_detector()

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
        ):
            await pipeline.start()
            assert pipeline.state == PipelineState.RUNNING

            await asyncio.sleep(0.05)
            await pipeline.stop()
            assert pipeline.state == PipelineState.STOPPED

    async def test_start_failure_sets_error(self) -> None:
        pipeline = DetectionPipeline(AppConfig())
        mock_cam = MagicMock()
        mock_cam.open.side_effect = RuntimeError("no camera")

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=MagicMock()),
        ):
            await pipeline.start()
            assert pipeline.state == PipelineState.ERROR


class TestPipelineDetection:
    async def test_detects_and_dispatches(self) -> None:
        config = AppConfig(cooldown=CooldownConfig(seconds=0))
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera(stop_after=1, pipeline=pipeline)
        mock_det = _make_mock_detector()

        mock_action = MagicMock()
        mock_action.execute = AsyncMock()
        mock_action.name = "test_action"

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[mock_action]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        mock_action.execute.assert_called_once()
        assert pipeline.stats.detection_count == 1
        assert pipeline.stats.last_detection_time is not None

    async def test_respects_cooldown(self) -> None:
        config = AppConfig(cooldown=CooldownConfig(seconds=300))
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera(stop_after=3, pipeline=pipeline)
        mock_det = _make_mock_detector()

        mock_action = MagicMock()
        mock_action.execute = AsyncMock()
        mock_action.name = "test_action"

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[mock_action]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        # Should fire only once despite 3 detections (cooldown blocks repeats)
        mock_action.execute.assert_called_once()

    async def test_roi_filtering(self) -> None:
        roi = RoiConfig(
            enabled=True,
            polygon=[[0.0, 0.0], [0.05, 0.0], [0.05, 0.05], [0.0, 0.05]],
            min_overlap=0.5,
        )
        config = AppConfig(
            detection=DetectionConfig(roi=roi),
            cooldown=CooldownConfig(seconds=0),
        )
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera(stop_after=1, pipeline=pipeline)
        # Detection bbox [0.1, 0.2, 0.5, 0.6] is outside the tiny ROI
        mock_det = _make_mock_detector()

        mock_action = MagicMock()
        mock_action.execute = AsyncMock()
        mock_action.name = "test_action"

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[mock_action]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        mock_action.execute.assert_not_called()

    async def test_handles_camera_failure(self) -> None:
        pipeline = DetectionPipeline(AppConfig())
        mock_cam = MagicMock()
        mock_cam.open = MagicMock()
        mock_cam.close = MagicMock()

        call_count = 0

        def grab_none_then_stop() -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                pipeline._stop_event.set()
            return None

        mock_cam.grab_frame = MagicMock(side_effect=grab_none_then_stop)
        mock_det = MagicMock()
        mock_det.load = MagicMock()
        mock_det.unload = MagicMock()

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        # Pipeline should stop cleanly, not error
        assert pipeline.state == PipelineState.STOPPED


class TestPipelineAutoRestart:
    async def test_recovers_from_transient_error(self) -> None:
        """Pipeline restarts after a single crash and continues running."""
        config = AppConfig()
        pipeline = DetectionPipeline(config)
        mock_cam = MagicMock()
        mock_cam.open = MagicMock()
        mock_cam.close = MagicMock()
        mock_cam.grab_frame = MagicMock(return_value=None)
        mock_det = MagicMock()
        mock_det.load = MagicMock()
        mock_det.unload = MagicMock()

        call_count = 0

        async def detection_loop_side_effect() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient camera glitch")
            # Second call: run briefly then let stop_event end it
            while not pipeline._stop_event.is_set():
                await asyncio.sleep(0.01)

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(
                pipeline,
                "_detection_loop",
                side_effect=detection_loop_side_effect,
            ),
            patch.object(pipeline, "_stream_loop", new_callable=AsyncMock),
            patch("couch_hound.pipeline._BASE_BACKOFF_SECS", 0.01),
        ):
            await pipeline.start()
            # Let it crash once and restart
            await asyncio.sleep(0.2)
            assert pipeline.state == PipelineState.RUNNING
            await pipeline.stop()

        assert pipeline.state == PipelineState.STOPPED
        assert call_count == 2  # crashed once, recovered once

    async def test_gives_up_after_max_retries(self) -> None:
        """Pipeline enters ERROR state after exhausting retries."""
        config = AppConfig()
        pipeline = DetectionPipeline(config)
        mock_cam = MagicMock()
        mock_cam.open = MagicMock()
        mock_cam.close = MagicMock()
        mock_det = MagicMock()
        mock_det.load = MagicMock()
        mock_det.unload = MagicMock()

        async def always_crash() -> None:
            raise RuntimeError("persistent failure")

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_detection_loop", side_effect=always_crash),
            patch.object(pipeline, "_stream_loop", new_callable=AsyncMock),
            patch("couch_hound.pipeline._BASE_BACKOFF_SECS", 0.01),
            patch("couch_hound.pipeline._MAX_BACKOFF_SECS", 0.01),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        assert pipeline.state == PipelineState.ERROR


class TestTwoStageDetection:
    async def test_two_stage_finds_dog_via_anchor(self) -> None:
        """Two-stage: finds couch in stage 1, then dog in cropped stage 2."""
        two_stage = TwoStageConfig(
            enabled=True,
            anchor_label="couch",
            anchor_confidence=0.40,
            padding=0.1,
            second_stage_confidence=0.40,
        )
        config = AppConfig(
            detection=DetectionConfig(two_stage=two_stage),
            cooldown=CooldownConfig(seconds=0),
        )
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera(stop_after=1, pipeline=pipeline)

        # Stage 1 returns a couch; stage 2 (detect_region) returns a dog
        couch = Detection(
            label="couch", confidence=0.80, bbox=[0.1, 0.2, 0.9, 0.8], is_target=False
        )
        dog = Detection(label="dog", confidence=0.75, bbox=[0.2, 0.3, 0.6, 0.7], is_target=True)

        mock_det = MagicMock()
        mock_det.load = MagicMock()
        mock_det.unload = MagicMock()
        mock_det.detect_with_threshold = MagicMock(return_value=[couch])
        mock_det.detect_region = MagicMock(return_value=[dog])

        mock_action = MagicMock()
        mock_action.execute = AsyncMock()
        mock_action.name = "test_action"

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[mock_action]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        # Dog was detected via two-stage and action fired
        mock_action.execute.assert_called_once()
        assert pipeline.stats.detection_count == 1
        # detect_region was called with the couch bbox
        mock_det.detect_region.assert_called()

    async def test_two_stage_falls_back_when_no_anchor(self) -> None:
        """Two-stage falls back to normal detection when no anchor found."""
        two_stage = TwoStageConfig(
            enabled=True,
            anchor_label="couch",
            anchor_confidence=0.40,
        )
        config = AppConfig(
            detection=DetectionConfig(two_stage=two_stage),
            cooldown=CooldownConfig(seconds=0),
        )
        pipeline = DetectionPipeline(config)
        mock_cam = _make_mock_camera(stop_after=1, pipeline=pipeline)

        dog = Detection(label="dog", confidence=0.70, bbox=[0.1, 0.2, 0.5, 0.6], is_target=True)

        mock_det = MagicMock()
        mock_det.load = MagicMock()
        mock_det.unload = MagicMock()
        # Stage 1: no couch found
        mock_det.detect_with_threshold = MagicMock(return_value=[])
        # Fallback single-stage finds a dog
        mock_det.detect = MagicMock(return_value=[dog])

        mock_action = MagicMock()
        mock_action.execute = AsyncMock()
        mock_action.name = "test_action"

        with (
            patch("couch_hound.pipeline.Camera", return_value=mock_cam),
            patch("couch_hound.pipeline.Detector", return_value=mock_det),
            patch.object(pipeline, "_build_actions", return_value=[mock_action]),
        ):
            await pipeline.start()
            assert pipeline._task is not None
            await pipeline._task

        # Fell back to single-stage and still detected
        mock_det.detect.assert_called()
        mock_action.execute.assert_called_once()
