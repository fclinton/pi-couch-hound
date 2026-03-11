# Pi Couch Hound — Technical Specification

A Raspberry Pi-powered dog detector that catches your furry couch potato in the act and triggers configurable actions — play sounds, run scripts, or whatever punishment fits the crime.

## Overview

Pi Couch Hound uses a camera connected to a Raspberry Pi to continuously monitor a couch (or any forbidden zone). When a dog is detected in the frame, the system triggers a configurable chain of actions: playing a sound, sending a notification, running an arbitrary script, or activating GPIO-connected devices.

The system is split into a **Python backend** (FastAPI) that handles detection and actions, and a **React TypeScript frontend** (Vite + React) that serves as the single control surface for all configuration, monitoring, and management. There is no need to edit YAML files by hand — everything is driven from the browser.

## Architecture

```
                        ┌──────────────────────────────────────────┐
                        │           React TS Frontend              │
                        │  (Vite SPA served by FastAPI static)     │
                        │                                          │
                        │  ┌──────────┐ ┌────────┐ ┌───────────┐  │
                        │  │ Live View│ │ Events │ │  Settings │  │
                        │  │ + ROI    │ │ Log    │ │  (all cfg)│  │
                        │  └────┬─────┘ └───┬────┘ └─────┬─────┘  │
                        └───────┼───────────┼─────────────┼────────┘
                           WSS  │    REST   │      REST   │
                        ┌───────┼───────────┼─────────────┼────────┐
                        │       ▼           ▼             ▼        │
                        │            FastAPI Backend                │
                        │                                          │
                        │  ┌─────────┐  ┌──────────┐  ┌────────┐  │
                        │  │ Camera  │  │ Detector │  │ Action │  │
                        │  │ Grabber │─▶│ (TFLite) │─▶│ Disp.  │  │
                        │  └─────────┘  └──────────┘  └───┬────┘  │
                        │                                  │       │
                        │       ┌──────┬──────┬──────┬─────┘       │
                        │       ▼      ▼      ▼      ▼            │
                        │    Sound  Script   HTTP   GPIO           │
                        │    Player Runner  /MQTT   Out            │
                        └──────────────────────────────────────────┘
```

### Components

| Component | Responsibility |
|---|---|
| **Frame Grabber** | Captures frames from the camera at a configurable interval |
| **Dog Detector** | Runs a TFLite object-detection model to identify dogs in a frame |
| **Cooldown Manager** | Prevents action spam by enforcing a minimum interval between triggers |
| **Action Dispatcher** | Evaluates which actions to fire and executes them |
| **Event Logger** | Records every detection event with timestamp, confidence, and snapshot |
| **Config Manager** | Loads, validates, persists, and hot-reloads `config.yaml` via API |
| **FastAPI Backend** | REST API + WebSocket for the React frontend |
| **React Frontend** | SPA for live view, event history, and full system configuration |

## Detection Engine

### Model

- **Default model:** MobileNet SSD v2 (COCO) compiled to TensorFlow Lite — already knows the `dog` class out of the box, runs comfortably on a Pi 4/5 with no accelerator.
- **Optional accelerator:** Google Coral USB TPU via `tflite_runtime` Edge TPU delegate for higher FPS.
- **Custom model support:** Users can upload any TFLite model + labels file through the web UI and map its label index via the settings page.

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
    → push event via WebSocket to connected clients
```

### Region of Interest (ROI)

Users draw a polygon ROI directly on the live camera feed in the React UI. A detection only triggers actions if the dog's bounding box overlaps the ROI by a configurable percentage. This prevents false triggers when the dog walks past the couch versus being *on* it.

## Configuration

### Storage

All configuration lives in `config.yaml` at the project root, but users **never need to edit it by hand**. The React settings UI is the primary interface — every save writes back to the YAML and hot-reloads the detection pipeline.

### Schema

```yaml
# ── Camera ──────────────────────────────────────────
camera:
  source: 0                    # 0 = Pi camera, /dev/video1, or RTSP URL
  resolution: [1280, 720]
  capture_interval: 0.5        # seconds between frame captures

# ── Detection ───────────────────────────────────────
detection:
  model: models/ssd_mobilenet_v2.tflite
  labels: models/coco_labels.txt
  target_label: dog
  confidence_threshold: 0.60
  use_coral: false
  roi:
    enabled: false
    polygon: [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]]
    min_overlap: 0.3

# ── Cooldown ────────────────────────────────────────
cooldown:
  seconds: 30

# ── Actions ─────────────────────────────────────────
actions:
  - name: play_sound
    type: sound
    enabled: true
    sound_file: sounds/get_off_couch.wav
    volume: 80

  - name: take_snapshot
    type: snapshot
    enabled: true
    save_dir: snapshots/
    max_kept: 500

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
    timeout: 10

  - name: gpio_buzzer
    type: gpio
    enabled: false
    pin: 17
    mode: pulse
    duration: 2.0

# ── Web Server ──────────────────────────────────────
web:
  host: 0.0.0.0
  port: 8080
  auth:
    enabled: false
    username: admin
    password_hash: ""          # bcrypt hash, set via UI

# ── Logging ─────────────────────────────────────────
logging:
  level: INFO
  file: logs/couch-hound.log
  max_size_mb: 50
  backup_count: 3
```

### Template Variables

Action fields that accept strings support template variables:

| Variable | Description |
|---|---|
| `{{timestamp}}` | ISO 8601 detection time |
| `{{confidence}}` | Detection confidence (0.0–1.0) |
| `{{snapshot_path}}` | Path to saved snapshot image |
| `{{label}}` | Detected object label |
| `{{bbox}}` | Bounding box as `[x1, y1, x2, y2]` |

## Action Types

### `sound`
Plays an audio file through the Pi's audio output using `pygame.mixer`. Supports WAV and MP3. Users can upload sound files through the settings UI.

### `snapshot`
Saves the detection frame as a JPEG to disk. Auto-prunes old snapshots when `max_kept` is exceeded (oldest deleted first).

### `http`
Sends an HTTP request. Useful for push notifications (ntfy.sh, Pushover, IFTTT), webhooks, or Home Assistant integration.

### `mqtt`
Publishes a message to an MQTT broker. Designed for integration with Home Assistant, Node-RED, or any MQTT-based automation system.

### `script`
Runs an arbitrary shell command or script. Executed in a subprocess with a configurable timeout to prevent hangs.

### `gpio`
Drives a GPIO pin on the Pi. Three modes:
- **pulse**: Set HIGH for `duration` seconds, then LOW.
- **toggle**: Flip the current state.
- **momentary**: Set HIGH, wait `duration`, set LOW.

## Backend API (FastAPI)

### REST Endpoints

#### System

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/status` | System status: uptime, detection count, last event, CPU/mem/temp |
| `POST` | `/api/test-actions` | Fire all enabled actions once (testing without a real detection) |
| `POST` | `/api/restart` | Restart the detection pipeline (no process restart) |

#### Configuration — Full CRUD from the Web

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/config` | Return the full current configuration as JSON |
| `PUT` | `/api/config` | Replace the entire configuration, validate, persist to YAML, hot-reload |
| `PATCH` | `/api/config/:section` | Partially update a config section (`camera`, `detection`, `cooldown`, `actions`, `web`, `logging`) |

#### Actions — Manage Individual Actions

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/actions` | List all configured actions |
| `POST` | `/api/actions` | Create a new action |
| `PUT` | `/api/actions/:name` | Update an existing action |
| `DELETE` | `/api/actions/:name` | Remove an action |
| `POST` | `/api/actions/:name/test` | Test-fire a single action |
| `PATCH` | `/api/actions/:name/toggle` | Enable/disable an action |

#### Events

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/events` | Paginated event list (`?limit=`, `?offset=`, `?since=`, `?until=`) |
| `GET` | `/api/events/:id` | Single event detail |
| `DELETE` | `/api/events/:id` | Delete an event and its snapshot |
| `DELETE` | `/api/events` | Bulk delete events (`?before=` timestamp) |
| `GET` | `/api/events/stats` | Aggregate stats: detections per hour/day, peak times, avg confidence |

#### Snapshots

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/snapshots/:filename` | Serve a snapshot image |

#### File Uploads

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/upload/sound` | Upload a sound file (WAV/MP3) to `sounds/` |
| `POST` | `/api/upload/model` | Upload a custom TFLite model + labels to `models/` |
| `GET` | `/api/sounds` | List available sound files |
| `GET` | `/api/models` | List available TFLite models |

#### ROI

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/roi` | Get the current ROI polygon |
| `PUT` | `/api/roi` | Save a new ROI polygon (from the canvas editor) |
| `DELETE` | `/api/roi` | Clear the ROI (disable zone filtering) |

#### Auth

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Authenticate, returns a JWT |
| `POST` | `/api/auth/change-password` | Update password (requires current password) |
| `GET` | `/api/auth/status` | Check if auth is enabled and if the current session is valid |

### WebSocket

| Endpoint | Description |
|---|---|
| `WS /ws/stream` | Live MJPEG frames as binary messages with detection bounding box overlay |
| `WS /ws/events` | Real-time detection event push (JSON messages) |
| `WS /ws/status` | Periodic system status updates (CPU, mem, temp, pipeline state) |

#### Streaming Architecture

The backend uses **MJPEG over WebSocket** — each frame is an independently-decodable JPEG sent as a binary WS message. This was chosen over WebRTC because:
- Zero additional dependencies (FastAPI WS + OpenCV `cv2.imencode` already in the project)
- aiortc has documented performance issues on Raspberry Pi ARM
- At the target frame rates, H.264 inter-frame compression provides minimal benefit
- The `ConnectionManager` abstraction keeps transport behind `broadcast_frame(bytes)`, making it straightforward to swap to WebRTC in the future if needed

**Decoupled frame rates:** The stream loop and detection loop run independently:
- **Detection loop** runs at `camera.capture_interval` (default 0.5s = ~2 FPS). Grabs a frame, runs TFLite inference, filters by ROI, applies cooldown, dispatches actions. Updates a cached `last_detections` list after each pass.
- **Stream loop** runs at ~15 FPS when clients are connected. Grabs a fresh frame, overlays the cached `last_detections` as bounding boxes, JPEG-encodes, and broadcasts to all `/ws/stream` clients. When no clients are connected, the loop idles (sleeps 0.5s between checks).

Both loops share the same `Camera` instance and run as concurrent asyncio tasks within the pipeline.

#### `/ws/stream` Protocol

- **Transport:** Binary WebSocket messages
- **Format:** Each message is a complete JPEG image (starts with `\xff\xd8`, ends with `\xff\xd9`)
- **Frame rate:** ~15 FPS when pipeline is running and clients are connected
- **Overlays:** Bounding boxes and confidence labels are burned into the JPEG by the backend (green rectangles with `"label 0.XX"` text)
- **Flow:** Server-push only. Client keeps the connection alive by staying connected; no client-to-server messages required.
- **Frontend implementation:** Receive binary message → `new Blob([data], {type: 'image/jpeg'})` → `URL.createObjectURL(blob)` → set as `<img src>`. Revoke the previous object URL on each frame to prevent memory leaks.

#### `/ws/events` Protocol

- **Transport:** Text WebSocket messages (JSON)
- **Format:**
  ```json
  {
    "timestamp": "2026-03-11T14:23:01.123456+00:00",
    "label": "dog",
    "confidence": 0.92,
    "bbox": [0.12, 0.34, 0.56, 0.78]
  }
  ```
- **Frequency:** Fires on each detection that passes cooldown (not every frame — only when actions are dispatched)
- **`bbox`:** Normalized `[x1, y1, x2, y2]` coordinates in `[0, 1]` range

#### `/ws/status` Protocol

- **Transport:** Text WebSocket messages (JSON)
- **Format:**
  ```json
  {
    "cpu_percent": 42.1,
    "memory_percent": 61.3,
    "temperature": 58.2,
    "pipeline_state": "running",
    "detection_count": 7,
    "last_detection_time": "2026-03-11T14:23:01.123456+00:00"
  }
  ```
- **Frequency:** Every 2 seconds
- **`temperature`:** Celsius from `/sys/class/thermal/thermal_zone0/temp`, or `null` if unavailable (non-Pi hardware)
- **`pipeline_state`:** One of `"running"`, `"stopped"`, `"error"`

#### Frontend WebSocket Implementation Guide

Recommended hook pattern for the React frontend:

1. **`useWebSocket(path, options?)`** — Generic reconnecting WebSocket hook:
   - Build WS URL from `window.location` (`ws://` or `wss://` + host + path)
   - Manage connect/disconnect in `useEffect`, cleanup on unmount
   - Reconnect on close with exponential backoff (1s → 2s → 4s, capped at 30s)
   - Return `{ connected, lastMessage }`

2. **`useStream()`** — Wraps `useWebSocket('/ws/stream', { binary: true })`:
   - On each binary message: create `Blob` → `URL.createObjectURL`
   - Store current URL in ref, revoke previous URL to prevent memory leaks
   - Expose `{ frameUrl: string | null, connected: boolean }`

3. **`<VideoFeed />`** component — Uses `useStream()`, renders `<img src={frameUrl} />`

## React TypeScript Frontend

### Tech Stack

| Tool | Purpose |
|---|---|
| **Vite** | Build tooling and dev server |
| **React 18** | UI framework |
| **TypeScript** | Type safety |
| **React Router** | Client-side routing |
| **TanStack Query** | Server state management, caching, and mutations |
| **Zustand** | Lightweight client state (WebSocket connection, UI state) |
| **Tailwind CSS** | Utility-first styling |
| **shadcn/ui** | Accessible component primitives (forms, dialogs, toasts) |
| **Recharts** | Event statistics charts |

### Pages & Routes

| Route | Page | Description |
|---|---|---|
| `/` | **Dashboard** | Live camera feed with detection overlay, system status cards, recent events ticker |
| `/events` | **Events** | Filterable, paginated event table with snapshot thumbnails. Click to expand detail view. Bulk delete controls. |
| `/events/:id` | **Event Detail** | Full snapshot, bounding box visualization, metadata, actions fired |
| `/events/stats` | **Statistics** | Charts: detections per hour/day, confidence distribution, peak activity times |
| `/settings` | **Settings** | Tabbed settings panel (see below) |
| `/settings/actions` | **Action Builder** | Visual action editor — add, edit, delete, reorder, test, toggle actions |
| `/login` | **Login** | Auth form (only shown when auth is enabled) |

### Settings Page — Tabs

The settings page is the central control panel. Every field maps to a `config.yaml` key and changes are applied live via `PATCH /api/config/:section`.

#### Camera Tab

| Control | Type | Maps to |
|---|---|---|
| Camera source | Text input + dropdown (Pi cam / USB / RTSP) | `camera.source` |
| Resolution | Preset dropdown (480p, 720p, 1080p) + custom | `camera.resolution` |
| Capture interval | Slider (0.1–5.0s) | `camera.capture_interval` |
| Preview | Live thumbnail showing current camera output | — |

#### Detection Tab

| Control | Type | Maps to |
|---|---|---|
| Model | Dropdown of uploaded models | `detection.model` |
| Labels file | Auto-paired with model | `detection.labels` |
| Upload model | File upload (`.tflite` + `.txt`) | — |
| Target label | Dropdown populated from labels file | `detection.target_label` |
| Confidence threshold | Slider (0.0–1.0) with live preview of detections at current threshold | `detection.confidence_threshold` |
| Use Coral TPU | Toggle switch | `detection.use_coral` |

#### ROI Tab

| Control | Type | Maps to |
|---|---|---|
| Enable ROI | Toggle switch | `detection.roi.enabled` |
| ROI editor | Canvas overlay on live feed — click to place polygon points, drag to adjust | `detection.roi.polygon` |
| Min overlap | Slider (0.0–1.0) | `detection.roi.min_overlap` |
| Clear ROI | Button | — |

#### Actions Tab

A card-based action builder:

- Each action is a card showing its name, type, enabled state, and a summary of its config.
- **Add Action** button opens a dialog with a type selector. Selecting a type shows the relevant form fields.
- Each card has: **Edit** (inline expand), **Test** (fire once), **Toggle** (enable/disable), **Delete** (with confirmation).
- Drag-to-reorder controls execution order.

Per-type form fields:

| Type | Fields |
|---|---|
| `sound` | Sound file (dropdown of uploaded files + upload button), volume slider |
| `snapshot` | Save directory, max kept (number input) |
| `http` | URL, method dropdown, headers (key-value editor), body (textarea with template var autocomplete) |
| `mqtt` | Broker host, port, topic, payload (textarea with template var autocomplete) |
| `script` | Command (text input), timeout slider |
| `gpio` | Pin number, mode dropdown, duration slider |

#### Cooldown Tab

| Control | Type | Maps to |
|---|---|---|
| Cooldown period | Slider (0–300s) + number input | `cooldown.seconds` |

#### System Tab

| Control | Type | Maps to |
|---|---|---|
| Log level | Dropdown (DEBUG/INFO/WARNING/ERROR) | `logging.level` |
| Log file max size | Number input (MB) | `logging.max_size_mb` |
| Log backup count | Number input | `logging.backup_count` |
| Enable auth | Toggle | `web.auth.enabled` |
| Change password | Password input + confirm | `web.auth.password_hash` |
| Server port | Number input (requires restart) | `web.port` |
| Restart pipeline | Button | — |
| System info | Read-only: Pi model, OS, Python version, disk usage, uptime | — |

### UI Components

#### Live View (`/`)

```
┌──────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────┐  ┌───────────┐  │
│  │                                 │  │  Status   │  │
│  │      Live Camera Feed           │  │  ───────  │  │
│  │      (WebSocket MJPEG)          │  │  FPS: 4.2 │  │
│  │                                 │  │  CPU: 42% │  │
│  │   ┌───────────┐                 │  │  Temp: 58°│  │
│  │   │  DOG 0.92 │ ← bbox overlay │  │  Mem: 61% │  │
│  │   └───────────┘                 │  │           │  │
│  │   ┌─ ─ ─ ─ ─ ─ ─ ─┐           │  │  Today: 7 │  │
│  │   ╎   ROI zone     ╎           │  │  detects  │  │
│  │   └─ ─ ─ ─ ─ ─ ─ ─┘           │  │           │  │
│  └─────────────────────────────────┘  └───────────┘  │
│                                                      │
│  Recent Events                                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                │
│  │thumb │ │thumb │ │thumb │ │thumb │ ← scrollable   │
│  │14:23 │ │13:01 │ │11:45 │ │09:30 │                │
│  │ 0.91 │ │ 0.87 │ │ 0.73 │ │ 0.95 │                │
│  └──────┘ └──────┘ └──────┘ └──────┘                │
└──────────────────────────────────────────────────────┘
```

#### Action Builder Card

```
┌─────────────────────────────────────────┐
│  🔊 play_sound                    [ON] │
│  ─────────────────────────────────────  │
│  Sound: get_off_couch.wav              │
│  Volume: ██████████░░ 80%              │
│                                         │
│  [Test ▶]     [Edit ✏️]     [Delete 🗑] │
└─────────────────────────────────────────┘
```

### Frontend Project Structure

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── package.json
│
├── src/
│   ├── main.tsx                    # App entry point
│   ├── App.tsx                     # Router + layout
│   │
│   ├── api/
│   │   ├── client.ts               # Axios/fetch wrapper with auth interceptor
│   │   ├── config.ts               # Config API hooks (TanStack Query)
│   │   ├── events.ts               # Events API hooks
│   │   ├── actions.ts              # Actions API hooks
│   │   ├── system.ts               # Status, upload, auth API hooks
│   │   └── types.ts                # Shared API response types
│   │
│   ├── hooks/
│   │   ├── useWebSocket.ts         # WebSocket connection manager
│   │   ├── useStream.ts            # Live video stream hook
│   │   └── useAuth.ts              # Auth state hook
│   │
│   ├── stores/
│   │   └── appStore.ts             # Zustand store (connection state, UI prefs)
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx           # Live view + status + recent events
│   │   ├── Events.tsx              # Event list page
│   │   ├── EventDetail.tsx         # Single event view
│   │   ├── EventStats.tsx          # Statistics / charts
│   │   ├── Settings.tsx            # Settings shell with tabs
│   │   └── Login.tsx               # Login form
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   │   ├── Header.tsx          # Top bar with connection indicator
│   │   │   └── Layout.tsx          # Shell layout
│   │   │
│   │   ├── live/
│   │   │   ├── VideoFeed.tsx       # WebSocket MJPEG renderer
│   │   │   ├── BboxOverlay.tsx     # Detection bounding box overlay
│   │   │   └── RoiEditor.tsx       # Interactive polygon editor on canvas
│   │   │
│   │   ├── events/
│   │   │   ├── EventTable.tsx      # Paginated event list
│   │   │   ├── EventCard.tsx       # Single event summary card
│   │   │   └── EventFilters.tsx    # Date range, confidence filters
│   │   │
│   │   ├── settings/
│   │   │   ├── CameraSettings.tsx
│   │   │   ├── DetectionSettings.tsx
│   │   │   ├── RoiSettings.tsx
│   │   │   ├── ActionsSettings.tsx
│   │   │   ├── ActionCard.tsx      # Individual action config card
│   │   │   ├── ActionForm.tsx      # Add/edit action dialog
│   │   │   ├── CooldownSettings.tsx
│   │   │   └── SystemSettings.tsx
│   │   │
│   │   ├── stats/
│   │   │   ├── DetectionChart.tsx  # Detections over time
│   │   │   └── ConfidenceChart.tsx # Confidence distribution
│   │   │
│   │   └── ui/                     # shadcn/ui primitives
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── dialog.tsx
│   │       ├── input.tsx
│   │       ├── select.tsx
│   │       ├── slider.tsx
│   │       ├── switch.tsx
│   │       ├── table.tsx
│   │       ├── tabs.tsx
│   │       └── toast.tsx
│   │
│   └── lib/
│       ├── utils.ts                # cn() helper, formatters
│       └── templates.ts            # Template variable definitions for autocomplete
│
└── public/
    └── favicon.svg
```

### Build & Deployment

The React app is built into static files that are served directly by FastAPI:

```bash
cd frontend && npm run build    # outputs to frontend/dist/
```

FastAPI mounts the `dist/` directory as static files and serves `index.html` as a catch-all for client-side routing:

```python
# In backend
app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

During development, Vite's dev server proxies API requests to the FastAPI backend:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/ws': { target: 'ws://localhost:8080', ws: true },
    },
  },
});
```

## Project Structure (Full)

```
pi-couch-hound/
├── config.yaml                     # User config (written by API, not hand-edited)
├── config.example.yaml             # Example config shipped with repo
├── pyproject.toml                  # Python package config
├── requirements.txt
│
├── couch_hound/                    # Python backend
│   ├── __init__.py
│   ├── main.py                     # Entry point — starts FastAPI + detection loop
│   ├── camera.py                   # Frame capture abstraction
│   ├── detector.py                 # TFLite inference wrapper
│   ├── actions/
│   │   ├── __init__.py             # Action registry
│   │   ├── base.py                 # Action base class
│   │   ├── sound.py
│   │   ├── snapshot.py
│   │   ├── http_action.py
│   │   ├── mqtt_action.py
│   │   ├── script.py
│   │   └── gpio.py
│   ├── cooldown.py                 # Cooldown manager
│   ├── config.py                   # YAML load/save/validate/hot-reload
│   ├── event_log.py                # SQLite-backed event store
│   ├── roi.py                      # Region-of-interest geometry
│   ├── templates.py                # Template variable rendering
│   └── api/
│       ├── __init__.py
│       ├── app.py                  # FastAPI app factory
│       ├── routes_config.py        # Config CRUD endpoints
│       ├── routes_actions.py       # Action management endpoints
│       ├── routes_events.py        # Event query endpoints
│       ├── routes_system.py        # Status, uploads, auth
│       ├── routes_roi.py           # ROI endpoints
│       ├── websocket.py            # WebSocket handlers (stream, events, status)
│       ├── auth.py                 # JWT auth middleware
│       └── schemas.py              # Pydantic request/response models
│
├── frontend/                       # React TypeScript frontend
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── package.json
│   └── src/
│       └── ...                     # (see Frontend Project Structure above)
│
├── models/
│   └── .gitkeep
├── sounds/
│   └── get_off_couch.wav
├── scripts/
│   └── example.sh
├── snapshots/                      # gitignored
├── logs/                           # gitignored
├── data/                           # SQLite db, gitignored
│
└── tests/
    ├── conftest.py
    ├── test_detector.py
    ├── test_actions.py
    ├── test_cooldown.py
    ├── test_config.py
    ├── test_roi.py
    ├── test_api_config.py
    ├── test_api_actions.py
    ├── test_api_events.py
    └── test_api_auth.py
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

### Backend (Python)

```
python >= 3.9
fastapi                   # API framework
uvicorn                   # ASGI server
tflite-runtime            # TFLite inference
opencv-python-headless    # Frame capture, resize, drawing
pyyaml                    # Config persistence
pydantic                  # Request/response validation
python-jose[cryptography] # JWT auth tokens
passlib[bcrypt]           # Password hashing
python-multipart          # File uploads
paho-mqtt                 # MQTT action (optional)
RPi.GPIO                  # GPIO action (optional, Pi-only)
pygame                    # Sound playback
```

### Frontend (Node.js)

```
node >= 18
react, react-dom          # UI framework
typescript                # Type safety
vite                      # Build tool
@tanstack/react-query     # Server state
zustand                   # Client state
react-router-dom          # Routing
tailwindcss               # Styling
recharts                  # Charts
```

## Installation & Running

```bash
# Clone
git clone https://github.com/<user>/pi-couch-hound.git
cd pi-couch-hound

# Backend
python -m venv venv
source venv/bin/activate
pip install -e .

# Download default model
python -m couch_hound.setup_model

# Frontend
cd frontend
npm install
npm run build
cd ..

# Copy example config (first run only)
cp config.example.yaml config.yaml

# Run
couch-hound                # opens on http://localhost:8080
```

### Development Mode

```bash
# Terminal 1: Backend with auto-reload
uvicorn couch_hound.api.app:create_app --factory --reload --port 8080

# Terminal 2: Frontend dev server (proxies API to :8080)
cd frontend && npm run dev   # opens on http://localhost:5173
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

- **Backend unit tests:** Each module is tested in isolation — detector with pre-recorded frames, actions with mocked subprocess/network calls, cooldown with controlled timestamps.
- **Backend API tests:** FastAPI `TestClient` for all endpoints, including config CRUD, action management, and auth flows.
- **Frontend unit tests:** Vitest + React Testing Library for component behavior and hook logic.
- **Integration tests:** End-to-end detection pipeline using fixture images containing dogs and non-dogs.
- **Hardware mocks:** GPIO and camera modules are mocked in CI; real hardware tests run manually on a Pi.

```bash
# Backend
pytest tests/ -v --cov=couch_hound

# Frontend
cd frontend && npm test
```

## Future Considerations

These are explicitly **not** in scope for v1 but are worth noting:

- **Multi-camera support** — monitor multiple zones from one Pi.
- **Training UI** — fine-tune the model on your specific dog/couch from the dashboard.
- **Cloud sync** — optional upload of snapshots/events to S3 or Google Drive.
- **Cat mode** — detect cats too (the model already supports it, just change `target_label`).
- **Scheduling** — only monitor during certain hours (e.g., when you're at work).
- **Multi-zone ROI** — define multiple forbidden zones with different action sets.
- **Mobile PWA** — add a service worker and manifest for installable mobile access.
