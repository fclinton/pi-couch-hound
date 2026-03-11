"""HTTP action — sends an HTTP request to a configured endpoint."""

from __future__ import annotations

import asyncio
import urllib.request
from typing import Any

from couch_hound.actions.base import BaseAction
from couch_hound.templates import render_template


class HttpAction(BaseAction):
    """Send an HTTP request with optional template-rendered body."""

    async def execute(self, context: dict[str, Any]) -> None:
        """Build and send the HTTP request."""
        tpl_ctx = context.get("template_context", {})

        url = render_template(self.config.url or "", tpl_ctx)
        method = (self.config.method or "POST").upper()
        body = render_template(self.config.body or "", tpl_ctx) if self.config.body else None
        headers: dict[str, str] = {}
        if self.config.headers:
            headers = {k: render_template(v, tpl_ctx) for k, v in self.config.headers.items()}

        await asyncio.to_thread(self._send_request, url, method, headers, body)

    @staticmethod
    def _send_request(
        url: str,
        method: str,
        headers: dict[str, str],
        body: str | None,
    ) -> None:
        """Blocking HTTP request via urllib."""
        data = body.encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {method} {url} returned status {resp.status}")
