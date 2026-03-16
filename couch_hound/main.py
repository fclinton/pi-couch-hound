"""Entry point - starts FastAPI server and detection loop."""

from typing import Any

import uvicorn

from couch_hound.config import load_config, setup_logging


def run() -> None:
    """Start the Couch Hound application."""
    config = load_config()
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
