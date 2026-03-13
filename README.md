# Pi Couch Hound

Raspberry Pi-powered dog detector that monitors your couch and triggers configurable actions when a dog is detected.

## Features

- Real-time dog detection using MobileNet SSD v2 (TFLite)
- Configurable actions: play sounds, take snapshots, HTTP webhooks, MQTT, GPIO, custom scripts
- Web UI for live camera feed, detection history, and configuration
- Optional Google Coral TPU acceleration
- Region-of-interest filtering with adjustable cooldown
- Runs as a systemd service for always-on monitoring

## Prerequisites

### Hardware

- Raspberry Pi 4 or 5 (2 GB+ RAM recommended)
- Pi Camera Module or USB V4L2-compatible camera
- MicroSD card (16 GB+)
- Optional: Google Coral USB Accelerator
- Optional: GPIO peripherals (buzzers, relays, LEDs)

### Software

- Python 3.12+
- Node.js 20+ and npm

## Quick Start

```bash
git clone https://github.com/your-org/pi-couch-hound.git
cd pi-couch-hound
./install.sh
```

The install script walks you through setup interactively. For unattended installs:

```bash
./install.sh --no-prompt                     # defaults only
./install.sh --with-coral --with-systemd     # with Coral TPU + auto-start service
```

Run `./install.sh --help` for all options.

## Manual Installation

If you prefer to install step-by-step:

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install the package
pip install .

# Optional: Coral TPU and/or GPIO support
pip install ".[coral,gpio]"

# 3. Download the detection model
python -m couch_hound.setup_model

# 4. Create your config file
cp config.example.yaml config.yaml
# Edit config.yaml to match your camera and preferences

# 5. Build the frontend
cd frontend && npm ci && npm run build && cd ..
```

## Configuration

Edit `config.yaml` to configure camera source, detection thresholds, actions, and more. See `config.example.yaml` for all available options with descriptions. The web UI also allows editing configuration at runtime.

## Running

### Development

```bash
source .venv/bin/activate
couch-hound
```

The web UI is available at `http://<your-pi-ip>:8080`.

### Production (systemd)

Set up the service with the install script:

```bash
./install.sh --with-systemd
```

Or manually:

```bash
sudo tee /etc/systemd/system/couch-hound.service > /dev/null <<EOF
[Unit]
Description=Pi Couch Hound - Dog Detector
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/couch-hound
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now couch-hound
```

Manage the service:

```bash
sudo systemctl status couch-hound
sudo systemctl restart couch-hound
sudo journalctl -u couch-hound -f
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint and format
ruff check couch_hound/ tests/
ruff format --check couch_hound/ tests/

# Type check
mypy couch_hound/

# Run tests
pytest tests/ -v

# Dev server with auto-reload
python -m uvicorn couch_hound.api.app:create_app --factory --port 8080 --reload

# Frontend dev server (separate terminal)
cd frontend && npm run dev
```

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.
