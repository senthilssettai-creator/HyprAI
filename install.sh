#!/bin/bash
# HyprAI Installation Script - Final Clean Version (Arch + Hyprland)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/.local/share/hyprai"
CONFIG_DIR="$HOME/.config/hyprai"
VENV_DIR="$INSTALL_DIR/venv"
DB_PATH="$INSTALL_DIR/context.db"

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

log() { echo -e "${BLUE}[*]${NC} $1"; }
ok() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }

# -----------------------------------------------------------
# SYSTEM CHECKS
# -----------------------------------------------------------

log "Checking system compatibility…"

if [ ! -f /etc/arch-release ]; then
    err "This installer only supports Arch Linux."
    exit 1
fi

if ! pgrep -x Hyprland >/dev/null; then
    warn "Hyprland is not running. Automation features may not work fully."
else
    ok "Hyprland detected"
fi

ok "System check passed"

# -----------------------------------------------------------
# SYSTEM DEPENDENCIES
# -----------------------------------------------------------

PAC_DEPS=(
    python python-pip python-virtualenv
    python-aiohttp python-websockets
    jq curl git grim slurp brightnessctl
)

AUR_DEPS=( ydotool wlrctl )

log "Checking pacman packages…"

MISSING=()
for pkg in "${PAC_DEPS[@]}"; do
    pacman -Qi "$pkg" &>/dev/null || MISSING+=("$pkg")
done

if [ ${#MISSING[@]} -gt 0 ]; then
    log "Installing: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
fi

log "Checking AUR packages…"

for pkg in "${AUR_DEPS[@]}"; do
    if ! command -v "$pkg" >/dev/null 2>&1; then
        warn "$pkg missing — installing from AUR"
        if command -v yay >/dev/null; then
            yay -S --needed --noconfirm "$pkg"
        elif command -v paru >/dev/null; then
            paru -S --needed --noconfirm "$pkg"
        else
            err "No AUR helper found. Install yay or paru."
            exit 1
        fi
    fi
done

ok "All dependencies installed"

# -----------------------------------------------------------
# DIRECTORIES
# -----------------------------------------------------------

log "Preparing directories…"
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$INSTALL_DIR/logs"
ok "Directories ready"

# -----------------------------------------------------------
# PYTHON VENV + DEPENDENCIES
# -----------------------------------------------------------

log "Creating Python virtual environment…"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

log "Installing Python dependencies…"

pip install --upgrade pip
pip install flask flask-cors python-dotenv pillow requests google-generativeai aiohttp websockets fastapi uvicorn

ok "Python venv ready"

# -----------------------------------------------------------
# INSTALL PROJECT FILES
# -----------------------------------------------------------

log "Copying HyprAI components…"

cp -r daemon "$INSTALL_DIR/"
cp -r web "$INSTALL_DIR/"
cp -r scripts "$INSTALL_DIR/"

ok "Project installed to $INSTALL_DIR"

# -----------------------------------------------------------
# GEMINI API CONFIG
# -----------------------------------------------------------

log "Gemini API Configuration"
echo -e "Get your key at: ${BLUE}https://makersuite.google.com/app/apikey${NC}"
read -p "Enter your Gemini API key: " API_KEY

if [ -z "$API_KEY" ]; then
    err "API key is required!"
    exit 1
fi

cat > "$CONFIG_DIR/config.ini" << EOF
[api]
gemini_key = $API_KEY
model = gemini-1.5-flash

[system]
db_path = $DB_PATH
port = 8765

[security]
enable_files = true
enable_shell = true
EOF

chmod 600 "$CONFIG_DIR/config.ini"
ok "Config saved to $CONFIG_DIR/config.ini"

# -----------------------------------------------------------
# DATABASE
# -----------------------------------------------------------

log "Initializing local database…"

python3 << PYEOF
import sqlite3
conn = sqlite3.connect("$DB_PATH")
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS command_history (id INTEGER PRIMARY KEY AUTOINCREMENT, command TEXT, output TEXT, success INTEGER, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_message TEXT, ai_response TEXT, context TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS learned_patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern_type TEXT, pattern_data TEXT, frequency INTEGER DEFAULT 1, last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

conn.commit()
conn.close()
PYEOF

ok "Database initialized"

# -----------------------------------------------------------
# INITIAL SYSTEM ANALYSIS
# -----------------------------------------------------------

log "Running first-time system analysis…"
python3 "$INSTALL_DIR/scripts/analyze_system.py" "$CONFIG_DIR" "$DB_PATH" || warn "Analysis script failed (non-fatal)"
ok "System analysis complete"

# -----------------------------------------------------------
# SYSTEMD USER SERVICE
# -----------------------------------------------------------

log "Creating systemd user service…"

SERVICE="$HOME/.config/systemd/user/hyprai.service"

cat > "$SERVICE" << EOF
[Unit]
Description=HyprAI Daemon - user service
After=graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/daemon/main.py
Restart=on-failure
RestartSec=5
Environment=WAYLAND_DISPLAY=wayland-0
Environment=HYPRLAND_INSTANCE_SIGNATURE=%t

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable hyprai.service

ok "Systemd service installed"

# -----------------------------------------------------------
# YDOTOOL FIX (NO SERVICE)
# -----------------------------------------------------------

log "Configuring ydotool permissions (no service)…"

sudo usermod -aG input "$USER"

sudo bash -c 'cat > /etc/udev/rules.d/70-ydotool.rules << EOF
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
EOF'

sudo udevadm control --reload-rules
sudo udevadm trigger

ok "ydotool configured — logout/login REQUIRED"

# -----------------------------------------------------------
# DONE
# -----------------------------------------------------------

echo -e "${GREEN}"
echo "=========================================="
echo "      HyprAI Installation Complete!"
echo "=========================================="
echo -e "${NC}"

echo -e "Start HyprAI:"
echo -e "  ${BLUE}systemctl --user start hyprai${NC}"

echo -e "\nDashboard:"
echo -e "  ${BLUE}http://localhost:8765${NC}"

echo -e "\n${YELLOW}Logout and log back in to activate ydotool permissions.${NC}"

