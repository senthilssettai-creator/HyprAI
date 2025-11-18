#!/bin/bash
# HyprAI Installation Script (Final Stable Version)
# Works on: Arch Linux + Hyprland (Wayland)
# Includes: Virtualenv, wlrctl automation, systemd user service

set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Colors
# ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[*]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
log_error()   { echo -e "${RED}[✗]${NC} $1"; }

# ──────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────
INSTALL_DIR="$HOME/.local/share/hyprai"
CONFIG_DIR="$HOME/.config/hyprai"
DB_PATH="$INSTALL_DIR/context.db"
VENV_DIR="$INSTALL_DIR/venv"

# ──────────────────────────────────────────────────────────────
# Logo
# ──────────────────────────────────────────────────────────────
echo -e "${BLUE}"
cat << "LOGO"
    __  __                 ___    ____
   / / / /_  ______  _____/   |  /  _/
  / /_/ / / / / __ \/ ___/ /| |  / /  
 / __  / /_/ / /_/ / /  / ___ |_/ /   
/_/ /_/\__, / .___/_/  /_/  |_/___/   
      /____/_/                         
Advanced AI Desktop Automation Suite
LOGO
echo -e "${NC}"

# ──────────────────────────────────────────────────────────────
# System Check
# ──────────────────────────────────────────────────────────────
log_info "Checking system…"

if [[ ! -f /etc/arch-release ]]; then
    log_error "This installer only supports Arch Linux."
    exit 1
fi

if ! pgrep -x Hyprland >/dev/null 2>&1; then
    log_warn "Hyprland is not running. The daemon will still install but automation may not function until you login again."
fi

log_success "System verified"

# ──────────────────────────────────────────────────────────────
# Dependencies (PACMAN + AUR)
# ──────────────────────────────────────────────────────────────
log_info "Checking dependencies…"

PACMAN_DEPS=(
    python python-psutil python-pip
    python-aiohttp python-websockets
    jq curl git
    grim slurp
    brightnessctl
    wtype
)
AUR_DEPS=(
    wlrctl
)

# Install pacman deps
MISSING=()
for p in "${PACMAN_DEPS[@]}"; do
    if ! pacman -Qi "$p" &>/dev/null; then
        MISSING+=("$p")
    fi
done

if (( ${#MISSING[@]} > 0 )); then
    log_info "Installing missing pacman packages: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
else
    log_success "All pacman dependencies already installed"
fi

# Install AUR deps
for aur in "${AUR_DEPS[@]}"; do
    if ! command -v "$aur" &>/dev/null; then
        log_warn "$aur is missing — installing from AUR"
        if command -v yay >/dev/null; then yay -S --noconfirm "$aur"
        elif command -v paru >/dev/null; then paru -S --noconfirm "$aur"
        else log_error "No AUR helper installed (yay/paru). Install one and re-run."; exit 1; fi
    fi
done

log_success "All system dependencies installed"

# ──────────────────────────────────────────────────────────────
# Create directories
# ──────────────────────────────────────────────────────────────
log_info "Preparing directories…"

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$INSTALL_DIR/logs"

log_success "Directories ready"

# ──────────────────────────────────────────────────────────────
# Create Virtual Environment (Fixes externally-managed-environment)
# ──────────────────────────────────────────────────────────────
log_info "Creating Python virtual environment…"

python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

log_success "Using Python venv: $VENV_DIR"

# ──────────────────────────────────────────────────────────────
# Python Packages
# ──────────────────────────────────────────────────────────────
log_info "Installing Python dependencies into venv…"

"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null

"$VENV_DIR/bin/pip" install \
    flask flask-cors python-dotenv pillow \
    requests google-generativeai psutil aiohttp websockets >/dev/null

log_success "Python dependencies installed"

# ──────────────────────────────────────────────────────────────
# Copy Project Files
# ──────────────────────────────────────────────────────────────
log_info "Installing HyprAI core files…"

cp -r daemon web scripts config "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/scripts/"*.sh || true

log_success "Files installed"

# ──────────────────────────────────────────────────────────────
# API KEY
# ──────────────────────────────────────────────────────────────
echo ""
log_info "Google Gemini API Setup"
echo -e "${YELLOW}Get your API key from:${NC} https://aistudio.google.com/"
echo ""

read -rp "Enter your Gemini API key: " API_KEY

if [[ -z "$API_KEY" ]]; then
    log_error "API key is required."
    exit 1
fi

cat > "$CONFIG_DIR/config.ini" << EOF
[api]
key = $API_KEY
model = gemini-1.5-flash

[system]
db_path = $DB_PATH
port = 8765
log_level = INFO

[automation]
enable_shell=true
enable_files=true
EOF

chmod 600 "$CONFIG_DIR/config.ini"

log_success "Config saved"

# ──────────────────────────────────────────────────────────────
# Initialize Database
# ──────────────────────────────────────────────────────────────
log_info "Initializing database…"

"$VENV_DIR/bin/python" << PYEOF
import sqlite3
db="$DB_PATH"
conn=sqlite3.connect(db)
cur=conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS command_history
(id INTEGER PRIMARY KEY AUTOINCREMENT,
 command TEXT,
 output TEXT,
 success INTEGER,
 ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

cur.execute("""CREATE TABLE IF NOT EXISTS system_state
(key TEXT PRIMARY KEY,
 value TEXT,
 updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

conn.commit()
conn.close()
print("DB OK:", db)
PYEOF

log_success "Database initialized"

# ──────────────────────────────────────────────────────────────
# System Analysis
# ──────────────────────────────────────────────────────────────
log_info "Running system analyzer…"

"$VENV_DIR/bin/python" "$INSTALL_DIR/scripts/analyze_system.py" "$CONFIG_DIR" "$DB_PATH"

log_success "System analysis complete"

# ──────────────────────────────────────────────────────────────
# Systemd Service
# ──────────────────────────────────────────────────────────────
log_info "Creating systemd service…"

mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/hyprai.service" << EOF
[Unit]
Description=HyprAI Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/daemon/main.py
Restart=on-failure
RestartSec=5
Environment=WAYLAND_DISPLAY=wayland-0
Environment=HYPRLAND_INSTANCE_SIGNATURE=${HYPRLAND_INSTANCE_SIGNATURE}

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now hyprai.service

log_success "Systemd service installed"

# ──────────────────────────────────────────────────────────────
# Finish
# ──────────────────────────────────────────────────────────────
echo -e "${GREEN}"
echo "=============================================="
echo "  🎉 HyprAI Installation Complete!"
echo "=============================================="
echo -e "${NC}"

echo -e "Start the service:"
echo -e "  ${BLUE}systemctl --user restart hyprai${NC}"

echo -e "Dashboard:"
echo -e "  ${BLUE}http://localhost:8765${NC}"

echo -e "${YELLOW}Log out and log back in for input permissions.${NC}"

