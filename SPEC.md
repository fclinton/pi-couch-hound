# Pi Couch Hound — Technical Specification

A Raspberry Pi-powered dog detector that catches your furry couch potato in the act and triggers configurable actions — play sounds, run scripts, or whatever punishment fits the crime.

## Overview

Pi Couch Hound uses a camera connected to a Raspberry Pi to continuously monitor a couch (or any forbidden zone). When a dog is detected in the frame, the system triggers a configurable chain of actions: playing a sound, sending a notification, running an arbitrary script, or activating GPIO-connected devices. Everything is configured through a single YAML file and managed via a lightweight local web dashboard.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────┐
│  Pi Camera  │────▶│  Frame Grab  │────▶│  Dog Detector  │────▶│  Action     │
│  / USB Cam  │     │  Loop        │     │  (TFLite)      │     │  Dispatcher │
└─────────────┘     └──────────────┘     └────────────────┘     └──────┬──────┘
                                                                       │
                                              ┌────────────────────────┼────────────┐
                                              │            │           │            │
                                         ┌────▼───┐  ┌────▼───┐  ┌───▼────┐  ┌───▼────┐
                                         │ Sound  │  │ Script │  │ Notify │  │  GPIO  │
                                         │ Player │  │ Runner │  │ (MQTT/ │  │ Output │
                                         └────────┘  └────────┘  │ HTTP)  │  └────────┘
                                                                  └────────┘
```

### Components

| Component | Responsibility |
|---|---|
| **Frame Grabber** | Captures frames from the camera at a configurable interval |
| **Dog Detector** | Runs a TFLite object-detection model to identify dogs in a frame |
| **Cooldown Manager** | Prevents action spam by enforcing a minimum interval between triggers |
| **Action Dispatcher** | Evaluates which actions to fire and executes them (sequentially or in parallel) |
| **Event Logger** | Records every detection event with timestamp, confidence, and snapshot |
| **Web Dashboard** | Local Flask app for live view, event history, and configuration |

## Detection Engine

### Model

- **Default model:** MobileNet SSD v2 (COCO) compiled to TensorFlow Lite — already knows the `dog` class out of the box, runs comfortably on a Pi 4/5 with no accelerator.
- **Optional accelerator:** Google Coral USB TPU via `tflite_runtime` Edge TPU delegate for higher FPS.
- **Custom model support:** Users can drop in any TFLite model and map its label index via config.

### Detection Pipeline

```
capture frame
    │
    ▼
resize to model input (300×300)
    │
    ▼
run inference
    │
    ▼
filter results:
  - class == "dog" (configurable label)
  - confidence >= threshold (default 0.60)
  - bounding box overlaps "forbidden zone" (optional ROI)
    │
    ▼
if detection passes filters AND cooldown has elapsed:
    → dispatch actions
    → log event
    → save snapshot
```

### Region of Interest (ROI)

Users can optionally define a polygon ROI in the config (or draw it on the web dashboard). A detection only triggers actions if the dog's bounding box overlaps the ROI by a configurable percentage. This prevents false triggers when the dog walks past the couch versus being *on* it.

## Configuration

All configuration lives in a single `config.yaml` at the project root.

```yaml
# ── Camera ──────────────────────────────────────────
camera:
  source: 0                    # 0 = Pi camera, or /dev/video1, or an RTSP URL
  resolution: [1280, 720]
  capture_interval: 0.5        # seconds between frame captures

# ── Detection ───────────────────────────────────────
detection:
  model: models/ssd_mobilenet_v2.tflite
  labels: models/coco_labels.txt
  target_label: dog             # what to detect
  confidence_threshold: 0.60    # minimum confidence to trigger
  use_coral: false              # enable Coral TPU delegate
  roi:                          # optional region of interest (normalized 0-1 coords)
    enabled: false
    polygon: [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]]
    min_overlap: 0.3            # fraction of bbox that must overlap ROI

# ── Cooldown ────────────────────────────────────────
cooldown:
  seconds: 30                  # minimum gap between triggers

# ── Actions ─────────────────────────────────────────
actions:
  - name: play_sound
    type: sound
    enabled: true
    sound_file: sounds/get_off_couch.wav
    volume: 80                 # 0-100

  - name: take_snapshot
    type: snapshot
    enabled: true
    save_dir: snapshots/
    max_kept: 500              # auto-prune oldest when exceeded

  - name: notify_phone
    type: http
    enabled: false
    url: "https://ntfy.sh/my-couch-hound"
    method: POST
    headers:
      Title: "Couch Hound Alert"
    body: "Dog detected on the couch at {{timestamp}}"

  - name: mqtt_publish
    type: mqtt
    enabled: false
    broker: localhost
    port: 1883
    topic: couch-hound/detection
    payload: '{"timestamp": "{{timestamp}}", "confidence": {{confidence}}}'

  - name: custom_script
    type: script
    enabled: false
    command: ./scripts/activate_sprinkler.sh
    timeout: 10                # kill script after N seconds

  - name: gpio_buzzer
    type: gpio
    enabled: false
    pin: 17
    mode: pulse                # pulse | toggle | momentary
    duration: 2.0              # seconds (for pulse/momentary)

# ── Web Dashboard ───────────────────────────────────
web:
  enabled: true
  host: 0.0.0.0
  port: 8080
  auth:
    enabled: false
    username: admin
    password: changeme         # plaintext here, hashed at runtime

# ── Logging ─────────────────────────────────────────
logging:
  level: INFO                  # DEBUG | INFO | WARNING | ERROR
  file: logs/couch-hound.log
  max_size_mb: 50
  backup_count: 3
```

### Template Variables

Action fields that accept strings support Jinja2-style template variables:

| Variable | Description |
|---|---|
| `{{timestamp}}` | ISO 8601 detection time |
| `{{confidence}}` | Detection confidence (0.0–1.0) |
| `{{snapshot_path}}` | Path to saved snapshot image |
| `{{label}}` | Detected object label |
| `{{bbox}}` | Bounding box as `[x1, y1, x2, y2]` |

## Action Types

### `sound`
Plays an audio file through the Pi's audio output using `aplay` or `pygame.mixer`. Supports WAV and MP3.

### `snapshot`
Saves the detection frame as a JPEG to disk. Auto-prunes old snapshots when `max_kept` is exceeded (oldest deleted first).

### `http`
Sends an HTTP request. Useful for push notifications (ntfy.sh, Pushover, IFTTT), webhooks, or Home Assistant integration.

### `mqtt`
Publishes a message to an MQTT broker. Designed for integration with Home Assistant, Node-RED, or any MQTT-based automation system.

### `script`
Runs an arbitrary shell command or script. Executed in a subprocess with a configurable timeout to prevent hangs. The process is killed if it exceeds the timeout.

### `gpio`
Drives a GPIO pin on the Pi. Three modes:
- **pulse**: Set HIGH for `duration` seconds, then LOW.
- **toggle**: Flip the current state.
- **momentary**: Set HIGH, wait `duration`, set LOW (alias for pulse with explicit reset).

## Web Dashboard

A minimal Flask application served locally on the Pi.

### Pages

| Route | Description |
|---|---|
| `GET /` | Live camera feed (MJPEG stream) with detection overlay and status |
| `GET /events` | Paginated event history with thumbnails, timestamps, and confidence |
| `GET /events/:id` | Single event detail with full snapshot |
| `GET /config` | View/edit `config.yaml` through a form UI |
| `POST /config` | Save updated config and hot-reload the detection loop |
| `GET /api/status` | JSON: uptime, detection count, last event, system stats |
| `GET /api/events` | JSON: event list (supports `?limit=`, `?offset=`, `?since=`) |
| `POST /api/test` | Fire all enabled actions once (for testing without a real detection) |

### Live View

The live view streams MJPEG from the camera with bounding boxes drawn over detected dogs. Users can draw/edit the ROI polygon directly on the video feed.

## Project Structure

```
pi-couch-hound/
├── config.yaml                 # User configuration
├── setup.py                    # Package setup
├── requirements.txt
│
├── couch_hound/
│   ├── __init__.py
│   ├── main.py                 # Entry point & orchestration loop
│   ├── camera.py               # Frame capture abstraction
│   ├── detector.py             # TFLite inference wrapper
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── base.py             # Action base class
│   │   ├── sound.py
│   │   ├── snapshot.py
│   │   ├── http_action.py
│   │   ├── mqtt_action.py
│   │   ├── script.py
│   │   └── gpio.py
│   ├── cooldown.py             # Cooldown manager
│   ├── config.py               # YAML loading, validation, hot-reload
│   ├── event_log.py            # SQLite-backed event store
│   ├── roi.py                  # Region-of-interest geometry
│   ├── templates.py            # Template variable rendering
│   └── web/
│       ├── __init__.py
│       ├── app.py              # Flask app factory
│       ├── routes.py           # Route handlers
│       ├── stream.py           # MJPEG streaming
│       ├── templates/
│       │   ├── base.html
│       │   ├── index.html
│       │   ├── events.html
│       │   └── config.html
│       └── static/
│           ├── style.css
│           └── app.js          # ROI drawing, live status polling
│
├── models/                     # TFLite models (downloaded at setup)
│   └── .gitkeep
├── sounds/                     # Audio files
│   └── get_off_couch.wav
├── scripts/                    # User-provided action scripts
│   └── example.sh
├── snapshots/                  # Detection snapshots (gitignored)
├── logs/                       # Log files (gitignored)
│
└── tests/
    ├── conftest.py
    ├── test_detector.py
    ├── test_actions.py
    ├── test_cooldown.py
    ├── test_config.py
    ├── test_roi.py
    └── test_web.py
```

## Data Storage

### Event Log (SQLite)

```sql
CREATE TABLE events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,  -- ISO 8601
    confidence    REAL    NOT NULL,
    label         TEXT    NOT NULL,
    bbox          TEXT    NOT NULL,  -- JSON array [x1, y1, x2, y2]
    snapshot_path TEXT,
    actions_fired TEXT    NOT NULL,  -- JSON array of action names
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX idx_events_timestamp ON events(timestamp);
```

The database file lives at `data/events.db` (auto-created on first run).

## Hardware Requirements

| Component | Required | Notes |
|---|---|---|
| Raspberry Pi 4 or 5 | Yes | 2 GB+ RAM recommended |
| Pi Camera Module or USB webcam | Yes | Any V4L2-compatible camera works |
| Speaker / audio output | For sound actions | 3.5mm, HDMI, or USB speaker |
| Google Coral USB Accelerator | No | Optional, boosts inference to ~60 FPS |
| GPIO peripherals | No | Buzzers, relays, LEDs — whatever you want |
| MicroSD card | Yes | 16 GB+ recommended |

## Software Dependencies

```
python >= 3.9
tflite-runtime           # TFLite inference (lighter than full TensorFlow)
opencv-python-headless    # Frame capture, resize, drawing
flask                     # Web dashboard
pyyaml                    # Config parsing
jinja2                    # Template rendering (bundled with Flask)
paho-mqtt                 # MQTT action (optional)
RPi.GPIO                  # GPIO action (optional, Pi-only)
pygame                    # Sound playback (alternative to aplay)
```

## Installation & Running

```bash
# Clone
git clone https://github.com/<user>/pi-couch-hound.git
cd pi-couch-hound

# Install
python -m venv venv
source venv/bin/activate
pip install -e .

# Download default model
python -m couch_hound.setup_model

# Copy and edit config
cp config.example.yaml config.yaml
nano config.yaml

# Run
couch-hound              # installed entry point
# or
python -m couch_hound
```

### systemd Service

```ini
[Unit]
Description=Pi Couch Hound - Dog Detector
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pi-couch-hound
ExecStart=/home/pi/pi-couch-hound/venv/bin/couch-hound
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Testing Strategy

- **Unit tests:** Each module is tested in isolation — detector with pre-recorded frames, actions with mocked subprocess/network calls, cooldown with controlled timestamps.
- **Integration tests:** End-to-end detection pipeline using fixture images containing dogs and non-dogs.
- **Hardware mocks:** GPIO and camera modules are mocked in CI; real hardware tests run manually on a Pi.
- **Test runner:** `pytest` with `pytest-cov` for coverage reporting.

```bash
pytest tests/ -v --cov=couch_hound
```

## Future Considerations

These are explicitly **not** in scope for v1 but are worth noting:

- **Multi-camera support** — monitor multiple zones from one Pi.
- **Training UI** — fine-tune the model on your specific dog/couch from the dashboard.
- **Cloud sync** — optional upload of snapshots/events to S3 or Google Drive.
- **Cat mode** — detect cats too (the model already supports it, just change `target_label`).
- **Scheduling** — only monitor during certain hours (e.g., when you're at work).
- **Multi-zone ROI** — define multiple forbidden zones with different action sets.
