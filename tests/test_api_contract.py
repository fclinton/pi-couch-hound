"""API contract tests — replicate exact frontend mutation payloads against real backend.

These tests mirror the JSON payloads each frontend component constructs and send
them to the real FastAPI TestClient.  They exist to catch mismatches between the
frontend API layer and backend expectations (e.g. PR #80 where ActionsTab sent a
raw array instead of ``{ actions: [...] }``).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from couch_hound.api.app import create_app
from couch_hound.config import ActionConfig, AppConfig

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Client pre-seeded with one action so toggle/test-fire/update tests work."""
    app = create_app()
    with TestClient(app) as client:
        app.state.config_path = tmp_path / "config.yaml"
        app.state.config = AppConfig(
            actions=[
                ActionConfig(name="bark_alarm", type="sound", enabled=True, sound_file="woof.wav"),
            ]
        )
        yield client


# ── Config PATCH contract tests (the PR #80 bug class) ───────────────────────


class TestContractPatchActions:
    """ActionsTab.tsx:289 — mutation.mutate({ section: "actions", data: { actions } })"""

    def test_patch_actions_with_wrapper_object(self, config_client: TestClient) -> None:
        """The correct payload: { actions: [{...}] }."""
        payload = {
            "actions": [
                {"name": "bark_alarm", "type": "sound", "enabled": True, "sound_file": "woof.wav"}
            ]
        }
        resp = config_client.patch("/api/config/actions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["actions"]) == 1
        assert data["actions"][0]["name"] == "bark_alarm"
        assert data["actions"][0]["type"] == "sound"

    def test_patch_actions_raw_array_rejected(self, config_client: TestClient) -> None:
        """PR #80 regression: sending a raw array must fail (422) because the
        endpoint declares ``body: dict[str, Any]``."""
        raw_array = [
            {"name": "bark_alarm", "type": "sound", "enabled": True, "sound_file": "woof.wav"}
        ]
        resp = config_client.patch("/api/config/actions", json=raw_array)
        assert resp.status_code == 422

    def test_patch_actions_roundtrip(self, config_client: TestClient) -> None:
        """Save actions via PATCH, then GET and verify they persist."""
        payload = {
            "actions": [
                {"name": "snap", "type": "snapshot", "enabled": True, "save_dir": "/tmp/snaps"},
                {"name": "beep", "type": "sound", "enabled": False, "sound_file": "beep.wav"},
            ]
        }
        resp = config_client.patch("/api/config/actions", json=payload)
        assert resp.status_code == 200

        resp = config_client.get("/api/config")
        assert resp.status_code == 200
        actions = resp.json()["actions"]
        assert len(actions) == 2
        assert actions[0]["name"] == "snap"
        assert actions[1]["name"] == "beep"


class TestContractPatchCamera:
    """CameraTab.tsx:27-34 — flat fields sent directly."""

    def test_patch_camera_flat_fields(self, config_client: TestClient) -> None:
        payload = {
            "source": 0,
            "resolution": [1920, 1080],
            "capture_interval": 1.0,
        }
        resp = config_client.patch("/api/config/camera", json=payload)
        assert resp.status_code == 200
        camera = resp.json()["camera"]
        assert camera["source"] == 0
        assert camera["resolution"] == [1920, 1080]
        assert camera["capture_interval"] == 1.0

    def test_patch_camera_string_source(self, config_client: TestClient) -> None:
        """CameraTab sends string source for RTSP URLs."""
        payload = {
            "source": "rtsp://cam.local/stream",
            "resolution": [1280, 720],
            "capture_interval": 0.5,
        }
        resp = config_client.patch("/api/config/camera", json=payload)
        assert resp.status_code == 200
        assert resp.json()["camera"]["source"] == "rtsp://cam.local/stream"

    def test_patch_camera_roundtrip(self, config_client: TestClient) -> None:
        payload = {"capture_interval": 2.5}
        config_client.patch("/api/config/camera", json=payload)
        resp = config_client.get("/api/config")
        assert resp.json()["camera"]["capture_interval"] == 2.5


class TestContractPatchCooldown:
    """CooldownTab.tsx:18 — { seconds: N }"""

    def test_patch_cooldown_flat_fields(self, config_client: TestClient) -> None:
        payload = {"seconds": 60}
        resp = config_client.patch("/api/config/cooldown", json=payload)
        assert resp.status_code == 200
        assert resp.json()["cooldown"]["seconds"] == 60

    def test_patch_cooldown_roundtrip(self, config_client: TestClient) -> None:
        config_client.patch("/api/config/cooldown", json={"seconds": 120})
        resp = config_client.get("/api/config")
        assert resp.json()["cooldown"]["seconds"] == 120


class TestContractPatchDetection:
    """DetectionTab.tsx:59-80 — full detection object with nested two_stage."""

    def test_patch_detection_flat_fields(self, config_client: TestClient) -> None:
        payload = {
            "model": "models/custom.tflite",
            "labels": "models/custom_labels.txt",
            "target_label": "cat",
            "confidence_threshold": 0.75,
            "use_coral": False,
            "roi": {
                "enabled": False,
                "polygon": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
                "min_overlap": 0.3,
            },
            "two_stage": {
                "enabled": True,
                "anchor_label": "couch",
                "anchor_confidence": 0.5,
                "anchor_padding": 0.1,
                "second_stage_confidence": 0.5,
                "min_contour_area": 1000,
                "contour_padding": 0.25,
                "debug_overlay": False,
            },
        }
        resp = config_client.patch("/api/config/detection", json=payload)
        assert resp.status_code == 200
        det = resp.json()["detection"]
        assert det["target_label"] == "cat"
        assert det["confidence_threshold"] == 0.75
        assert det["two_stage"]["enabled"] is True
        assert det["two_stage"]["anchor_confidence"] == 0.5


class TestContractPatchDetectionRoi:
    """RoiTab.tsx:25-33 — only roi sub-object sent to detection section."""

    def test_patch_roi_via_detection(self, config_client: TestClient) -> None:
        payload = {
            "roi": {
                "enabled": True,
                "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
                "min_overlap": 0.5,
            },
        }
        resp = config_client.patch("/api/config/detection", json=payload)
        assert resp.status_code == 200
        roi = resp.json()["detection"]["roi"]
        assert roi["enabled"] is True
        assert roi["min_overlap"] == 0.5


class TestContractPatchEscalation:
    """EscalationTab.tsx:23 — sends the escalation object directly (not wrapped)."""

    def test_patch_escalation_as_object(self, config_client: TestClient) -> None:
        payload = {
            "enabled": True,
            "reset_cooldown": 120,
            "levels": [
                {"delay": 0, "actions": ["bark_alarm"]},
                {"delay": 30, "actions": ["bark_alarm", "snap"]},
            ],
        }
        resp = config_client.patch("/api/config/escalation", json=payload)
        assert resp.status_code == 200
        esc = resp.json()["escalation"]
        assert esc["enabled"] is True
        assert esc["reset_cooldown"] == 120
        assert len(esc["levels"]) == 2


class TestContractPatchWeb:
    """Web section — flat merge of web fields."""

    def test_patch_web_port(self, config_client: TestClient) -> None:
        payload = {"port": 9090}
        resp = config_client.patch("/api/config/web", json=payload)
        assert resp.status_code == 200
        assert resp.json()["web"]["port"] == 9090


class TestContractPatchLogging:
    """Logging section — flat merge."""

    def test_patch_logging_level(self, config_client: TestClient) -> None:
        payload = {"level": "DEBUG"}
        resp = config_client.patch("/api/config/logging", json=payload)
        assert resp.status_code == 200
        assert resp.json()["logging"]["level"] == "DEBUG"


class TestContractPatchMonitoring:
    """Monitoring section — flat merge."""

    def test_patch_monitoring_config(self, config_client: TestClient) -> None:
        payload = {
            "enabled": False,
            "auto_disable": {"person_detection": True},
        }
        resp = config_client.patch("/api/config/monitoring", json=payload)
        assert resp.status_code == 200
        mon = resp.json()["monitoring"]
        assert mon["enabled"] is False
        assert mon["auto_disable"]["person_detection"] is True


class TestContractPatchUpdate:
    """Update section — flat merge."""

    def test_patch_update_config(self, config_client: TestClient) -> None:
        payload = {
            "enabled": True,
            "channel": "nightly",
            "check_interval_minutes": 30,
        }
        resp = config_client.patch("/api/config/update", json=payload)
        assert resp.status_code == 200
        upd = resp.json()["update"]
        assert upd["enabled"] is True
        assert upd["channel"] == "nightly"


# ── Auth contract tests ──────────────────────────────────────────────────────


class TestContractAuth:
    """Frontend auth mutations: setup, login, change-password."""

    def test_auth_setup(self, config_client: TestClient) -> None:
        """POST /api/auth/setup with { username, password }."""
        payload = {"username": "admin", "password": "secret123"}
        resp = config_client.post("/api/auth/setup", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_auth_login_after_setup(self, config_client: TestClient) -> None:
        """POST /api/auth/login with { username, password }."""
        config_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
        resp = config_client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret123"}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_auth_change_password(self, config_client: TestClient) -> None:
        """POST /api/auth/change-password with { current_password, new_password }."""
        setup_resp = config_client.post(
            "/api/auth/setup", json={"username": "admin", "password": "old123"}
        )
        token = setup_resp.json()["access_token"]
        resp = config_client.post(
            "/api/auth/change-password",
            json={"current_password": "old123", "new_password": "new456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"


# ── Actions CRUD contract tests ──────────────────────────────────────────────


class TestContractActionsCrud:
    """Frontend actions mutations: create, update, toggle, test-fire."""

    def test_create_action(self, config_client: TestClient) -> None:
        """POST /api/actions with a single ActionConfig object."""
        payload = {
            "name": "new_alert",
            "type": "script",
            "enabled": True,
            "command": "echo alert",
            "timeout": 10,
        }
        resp = config_client.post("/api/actions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["name"] == "new_alert"
        assert resp.json()["type"] == "script"

    def test_update_action(self, seeded_client: TestClient) -> None:
        """PUT /api/actions/{name} with updated ActionConfig."""
        payload = {
            "name": "bark_alarm",
            "type": "sound",
            "enabled": True,
            "sound_file": "loud_woof.wav",
            "volume": 80,
        }
        resp = seeded_client.put("/api/actions/bark_alarm", json=payload)
        assert resp.status_code == 200
        assert resp.json()["sound_file"] == "loud_woof.wav"

    def test_toggle_action(self, seeded_client: TestClient) -> None:
        """PATCH /api/actions/{name}/toggle — no body."""
        resp = seeded_client.patch("/api/actions/bark_alarm/toggle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "bark_alarm"
        assert data["enabled"] is False  # was True, now toggled

    def test_test_fire_action(self, seeded_client: TestClient) -> None:
        """POST /api/actions/{name}/test — no body."""
        resp = seeded_client.post("/api/actions/bark_alarm/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "bark_alarm"
        assert "success" in data


# ── Monitoring contract test ─────────────────────────────────────────────────


class TestContractMonitoringEndpoint:
    """Frontend useSetMonitoring — PUT /api/monitoring with { enabled: bool }."""

    def test_set_monitoring(self, config_client: TestClient) -> None:
        payload = {"enabled": True}
        resp = config_client.put("/api/monitoring", json=payload)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_disable_monitoring(self, config_client: TestClient) -> None:
        payload = {"enabled": False}
        resp = config_client.put("/api/monitoring", json=payload)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
