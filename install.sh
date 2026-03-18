#!/usr/bin/env bash
set -euo pipefail

# ── Colors ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Defaults ──────────────────────────────────────────
WITH_GPIO=false
WITH_SYSTEMD=false
NO_PROMPT=false
DEV_MODE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse Arguments ───────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --with-coral)
            echo -e "${BLUE}[INFO]${NC} Coral TPU support requires the system library libedgetpu."
            echo -e "${BLUE}[INFO]${NC} Install it with: sudo apt install libedgetpu1-std"
            ;;
        --with-gpio)    WITH_GPIO=true ;;
        --with-systemd) WITH_SYSTEMD=true ;;
        --no-prompt)    NO_PROMPT=true ;;
        --dev)          DEV_MODE=true ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-coral     Show instructions for Google Coral TPU setup"
            echo "  --with-gpio      Install Raspberry Pi GPIO support"
            echo "  --with-systemd   Install and enable systemd service"
            echo "  --no-prompt      Skip interactive prompts (use defaults + flags)"
            echo "  --dev            Developer mode: build frontend from source (requires Node.js/npm)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $arg"
            exit 1
            ;;
    esac
done

ask() {
    if [ "$NO_PROMPT" = true ]; then
        return 1
    fi
    local prompt="$1"
    read -r -p "$(echo -e "${BLUE}[?]${NC} ${prompt} [y/N] ")" answer
    [[ "$answer" =~ ^[Yy] ]]
}

cd "$SCRIPT_DIR"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Pi Couch Hound — Installer       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Check Prerequisites ───────────────────────────
info "Checking prerequisites..."

PYTHON=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=$("$cmd" -c 'import sys; print(sys.version_info.major)')
        minor=$("$cmd" -c 'import sys; print(sys.version_info.minor)')
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.12+ is required but not found."
    error "Install it with: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
ok "Python: $($PYTHON --version)"

# Check for uv
if command -v uv &>/dev/null; then
    ok "uv: $(uv --version)"
    USE_UV=true
else
    warn "uv not found — falling back to pip. Install uv for faster installs:"
    warn "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    USE_UV=false
fi

# Node.js/npm only required in dev mode or when frontend is not pre-built
if [ "$DEV_MODE" = true ] && [ ! -d "frontend/dist" ]; then
    if ! command -v node &>/dev/null; then
        error "Node.js is required for --dev mode but not found."
        error "Install it with: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - && sudo apt install -y nodejs"
        exit 1
    fi
    ok "Node.js: $(node --version)"

    if ! command -v npm &>/dev/null; then
        error "npm is required for --dev mode but not found."
        exit 1
    fi
    ok "npm: $(npm --version)"
fi
echo ""

# ── 2. Create Python venv & Install ──────────────────
EXTRAS=""
if [ "$WITH_GPIO" = true ] || { [ "$NO_PROMPT" = false ] && ask "Install Raspberry Pi GPIO support?"; }; then
    EXTRAS="gpio"
    WITH_GPIO=true
fi

if [ "$USE_UV" = true ]; then
    info "Installing Pi Couch Hound with uv..."
    if [ -n "$EXTRAS" ]; then
        uv sync --extra "$EXTRAS"
    else
        uv sync
    fi
else
    if [ -d ".venv" ]; then
        info "Python venv already exists at .venv/"
    else
        info "Creating Python virtual environment..."
        $PYTHON -m venv .venv
        ok "Virtual environment created at .venv/"
    fi

    # shellcheck disable=SC1091
    source .venv/bin/activate

    info "Installing Pi Couch Hound..."
    if [ -n "$EXTRAS" ]; then
        pip install --quiet ".[$EXTRAS]"
    else
        pip install --quiet .
    fi
fi
ok "Python package installed"
echo ""

# ── 4. Download Detection Model ──────────────────────
info "Downloading detection model..."
$PYTHON -m couch_hound.setup_model
ok "Detection model ready"
echo ""

# ── 5. Copy Config ───────────────────────────────────
if [ -f "config.yaml" ]; then
    warn "config.yaml already exists — skipping copy (edit it manually if needed)"
else
    cp config.example.yaml config.yaml
    ok "Created config.yaml from template — edit it to match your setup"
fi
echo ""

# ── 6. Build Frontend ────────────────────────────────
if [ -d "frontend/dist" ]; then
    ok "Pre-built frontend found at frontend/dist/"
elif [ "$DEV_MODE" = true ]; then
    info "Building frontend from source..."
    (cd frontend && npm ci --silent && npm run build --silent)
    ok "Frontend built to frontend/dist/"
else
    warn "frontend/dist/ not found. Use a release tarball or run with --dev to build from source."
fi
echo ""

# ── 7. systemd Service (optional) ────────────────────
if [ "$WITH_SYSTEMD" = true ] || { [ "$NO_PROMPT" = false ] && ask "Install as a systemd service (starts on boot)?"; }; then
    info "Setting up systemd service..."

    INSTALL_DIR="$SCRIPT_DIR"
    SERVICE_USER="$(whoami)"

    SERVICE_FILE="[Unit]
Description=Pi Couch Hound - Dog Detector
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/couch-hound
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"

    echo "$SERVICE_FILE" | sudo tee /etc/systemd/system/couch-hound.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now couch-hound
    ok "systemd service installed and started"
    info "Manage with: sudo systemctl {start|stop|restart|status} couch-hound"
    info "View logs:   sudo journalctl -u couch-hound -f"
else
    info "Skipping systemd setup — run manually with: couch-hound"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Installation complete!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "  Start:   source .venv/bin/activate && couch-hound"
echo "  Web UI:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8080"
echo "  Config:  config.yaml"
echo ""
