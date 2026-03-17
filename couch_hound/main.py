"""Entry point - starts FastAPI server and detection loop."""

import logging
import sys
from typing import Any

import uvicorn

from couch_hound.config import AppConfig, load_config, setup_logging

logger = logging.getLogger(__name__)


def run() -> None:
    """Start the Couch Hound application."""
    try:
        config = load_config()
    except Exception:
        print(  # noqa: T201
            "WARNING: Failed to load config, starting with defaults",
            file=sys.stderr,
        )
        logging.basicConfig(level=logging.WARNING)
        logger.exception("Config load failed, using defaults")
        config = AppConfig()
    setup_logging(config.logging)
    kwargs: dict[str, Any] = {
        "host": config.web.host,
        "port": config.web.port,
        "reload": False,
    }
    if config.web.ssl.enabled:
        from couch_hound.ssl_certs import ensure_ssl_files

        certfile, keyfile = ensure_ssl_files(config.web.ssl)
        kwargs["ssl_certfile"] = certfile
        kwargs["ssl_keyfile"] = keyfile
    uvicorn.run("couch_hound.api.app:create_app", factory=True, **kwargs)


if __name__ == "__main__":
    run()
