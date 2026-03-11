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
        pytest.raises(OSError, match="Connection refused"),
    ):
        await action.execute({})
