"""Entry point - starts FastAPI server and detection loop."""

import uvicorn

from couch_hound.config import load_config


def run() -> None:
    """Start the Couch Hound application."""
    config = load_config()
    uvicorn.run(
        "couch_hound.api.app:create_app",
        factory=True,
        host=config.web.host,
        port=config.web.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
