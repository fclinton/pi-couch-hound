"""Tests for the MqttAction."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from couch_hound.actions.mqtt import MqttAction
from couch_hound.config import ActionConfig


def _make_config(**kwargs: object) -> ActionConfig:
    return ActionConfig(name="test_mqtt", type="mqtt", **kwargs)


async def test_mqtt_publish_success() -> None:
    config = _make_config(
        broker="mqtt.local", port=1883, topic="couch/detect", payload='{"dog": true}'
    )
    action = MqttAction(config)

    with patch("paho.mqtt.publish.single") as mock_pub:
        await action.execute({})
        mock_pub.assert_called_once_with(
            "couch/detect", payload='{"dog": true}', hostname="mqtt.local", port=1883
        )


async def test_mqtt_template_rendering() -> None:
    config = _make_config(
        broker="mqtt.local",
        topic="couch/{{label}}",
        payload="confidence={{confidence}}",
    )
    action = MqttAction(config)

    ctx = {"template_context": {"label": "dog", "confidence": "0.9200"}}
    with patch("paho.mqtt.publish.single") as mock_pub:
        await action.execute(ctx)
        mock_pub.assert_called_once_with(
            "couch/dog", payload="confidence=0.9200", hostname="mqtt.local", port=1883
        )


async def test_mqtt_defaults() -> None:
    config = _make_config(topic="test/topic", payload="hello")
    action = MqttAction(config)

    with patch("paho.mqtt.publish.single") as mock_pub:
        await action.execute({})
        mock_pub.assert_called_once_with(
            "test/topic", payload="hello", hostname="localhost", port=1883
        )


async def test_mqtt_connection_error() -> None:
    config = _make_config(broker="bad.host", topic="t", payload="p")
    action = MqttAction(config)

    with (
        patch("paho.mqtt.publish.single", side_effect=OSError("Connection refused")),
        pytest.raises(RuntimeError, match="Connection refused"),
    ):
        await action.execute({})


async def test_mqtt_retries_on_transient_error() -> None:
    """MQTT action retries once on transient failure then succeeds."""
    config = _make_config(broker="mqtt.local", topic="t", payload="p")
    action = MqttAction(config)

    call_count = 0

    def _publish_side_effect(*args: object, **kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Transient failure")

    with patch("paho.mqtt.publish.single", side_effect=_publish_side_effect):
        await action.execute({})
    assert call_count == 2


async def test_mqtt_timeout() -> None:
    """MQTT action raises RuntimeError on publish timeout."""
    config = _make_config(broker="slow.host", topic="t", payload="p")
    action = MqttAction(config)

    import couch_hound.actions.mqtt as mqtt_mod

    original_timeout = mqtt_mod._PUBLISH_TIMEOUT
    mqtt_mod._PUBLISH_TIMEOUT = 0.1  # very short for testing

    def _slow_publish(*args: object, **kwargs: object) -> None:
        import time

        time.sleep(1)

    try:
        with (
            patch("paho.mqtt.publish.single", side_effect=_slow_publish),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            await action.execute({})
    finally:
        mqtt_mod._PUBLISH_TIMEOUT = original_timeout
