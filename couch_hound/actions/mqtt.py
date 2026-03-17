"""MQTT action — publishes a message to an MQTT broker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from couch_hound.actions.base import BaseAction
from couch_hound.templates import render_template

logger = logging.getLogger(__name__)

_PUBLISH_TIMEOUT = 10.0


class MqttAction(BaseAction):
    """Publish a message to an MQTT topic."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Render payload and publish to the configured broker."""
        tpl_ctx = context.get("template_context", {})

        topic = render_template(self.config.topic or "", tpl_ctx)
        payload = render_template(self.config.payload or "", tpl_ctx)
        broker = self.config.broker or "localhost"
        port = self.config.port or 1883

        async def _attempt() -> None:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._publish, broker, port, topic, payload),
                    timeout=_PUBLISH_TIMEOUT,
                )
            except TimeoutError:
                raise RuntimeError(f"MQTT publish to {broker}:{port}/{topic} timed out") from None

        await self._retry(_attempt)

    @staticmethod
    def _publish(broker: str, port: int, topic: str, payload: str) -> None:
        """Blocking MQTT publish via paho."""
        import paho.mqtt.publish as mqtt_publish

        try:
            mqtt_publish.single(topic, payload=payload, hostname=broker, port=port)
        except Exception as exc:
            raise RuntimeError(f"MQTT publish to {broker}:{port}/{topic} failed: {exc}") from exc
