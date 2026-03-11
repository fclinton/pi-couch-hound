"""MQTT action — publishes a message to an MQTT broker."""

from __future__ import annotations

import asyncio
from typing import Any

from couch_hound.actions.base import BaseAction
from couch_hound.templates import render_template


class MqttAction(BaseAction):
    """Publish a message to an MQTT topic."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Render payload and publish to the configured broker."""
        tpl_ctx = context.get("template_context", {})

        topic = render_template(self.config.topic or "", tpl_ctx)
        payload = render_template(self.config.payload or "", tpl_ctx)
        broker = self.config.broker or "localhost"
        port = self.config.port or 1883

        await asyncio.to_thread(self._publish, broker, port, topic, payload)

    @staticmethod
    def _publish(broker: str, port: int, topic: str, payload: str) -> None:
        """Blocking MQTT publish via paho."""
        import paho.mqtt.publish as mqtt_publish

        mqtt_publish.single(topic, payload=payload, hostname=broker, port=port)
