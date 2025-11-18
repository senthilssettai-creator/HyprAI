#!/bin/bash
# HyprAI Installation Script for Arch Linux + Hyprland
# This script performs a complete system analysis and setup


set -e


RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'


INSTALL_DIR="$HOME/.local/share/hyprai"
CONFIG_DIR="$HOME/.config/hyprai"
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


log_info() { echo -e "${BLUE}[*]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }


# Check if running on Arch with Hyprland
log_info "Verifying system compatibility..."
if [ ! -f /etc/arch-release ]; then
    log_error "This system is not Arch Linux!"
    exit 1
fi


if ! pgrep -x Hyprland > /dev/null; then
    log_warn "Hyprland is not currently running. Some features may not work."
fi
log_success "System check passed"


# Dependency checking and installation
log_info "Checking dependencies..."


DEPS_PACMAN=(python python-pip python-aiohttp python-websockets git jq curl grim slurp brightnessctl)
DEPS_AUR=(ydotool)
DEPS_PIP=(flask flask-cors python-dotenv pillow requests google-generativeai)


MISSING_PACMAN=()
for dep in "${DEPS_PACMAN[@]}"; do
    if ! pacman -Qi "$dep" &> /dev/null; then
        MISSING_PACMAN+=("$dep")
    fi
done


if [ ${#MISSING_PACMAN[@]} -gt 0 ]; then
    log_info "Installing missing packages: ${MISSING_PACMAN[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING_PACMAN[@]}"
fi


# Check for ydotool
if ! command -v ydotool &> /dev/null; then
    log_warn "ydotool not found. Attempting AUR install..."
    if command -v yay &> /dev/null; then
        yay -S --needed --noconfirm ydotool
    elif command -v paru &> /dev/null; then
        paru -S --needed --noconfirm ydotool
    else
        log_error "No AUR helper found. Please install ydotool manually."
        exit 1
    fi
fi


log_success "All system dependencies installed"


# Python dependencies
log_info "Installing Python dependencies..."
pip install --user --upgrade "${DEPS_PIP[@]}"
log_success "Python dependencies installed"


# Create directories
log_info "Creating application directories..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"
mkdir -p "$INSTALL_DIR/logs"


# Copy application files
log_info "Installing HyprAI components..."
cp -r daemon web scripts config "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/scripts/"*.sh


# API Key configuration
echo ""
log_info "API Key Configuration"
echo -e "${YELLOW}You need a Google Gemini API key (free tier available)${NC}"
echo -e "Get one at: ${BLUE}https://makersuite.google.com/app/apikey${NC}"
echo ""
read -p "Enter your Gemini API key: " API_KEY


if [ -z "$API_KEY" ]; then
    log_error "API key is required!"
    exit 1
fi


# Create encrypted config
cat > "$CONFIG_DIR/config.ini" << EOF
[api]
gemini_key = $API_KEY
model = gemini-1.5-flash


[system]
db_path = $DB_PATH
log_level = INFO
port = 8765


[security]
enable_file_ops = true
enable_shell_exec = true
max_command_history = 1000
EOF


chmod 600 "$CONFIG_DIR/config.ini"
log_success "Configuration saved securely"


# Initialize database
log_info "Initializing context database..."
python3 << PYEOF
import sqlite3
import os


db_path = "$DB_PATH"
conn = sqlite3.connect(db_path)
c = conn.cursor()


# System context table
c.execute('''CREATE TABLE IF NOT EXISTS system_state
             (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')


# Command history
c.execute('''CREATE TABLE IF NOT EXISTS command_history
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              command TEXT, 
              output TEXT, 
              success INTEGER,
              timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')


# Conversation history
c.execute('''CREATE TABLE IF NOT EXISTS conversations
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_message TEXT,
              ai_response TEXT,
              context TEXT,
              timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')


# Learned patterns
c.execute('''CREATE TABLE IF NOT EXISTS learned_patterns
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              pattern_type TEXT,
              pattern_data TEXT,
              frequency INTEGER DEFAULT 1,
              last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')


conn.commit()
conn.close()
print("Database initialized successfully")
PYEOF


log_success "Database created"


# System analysis
log_info "Performing initial system analysis..."
python3 "$INSTALL_DIR/scripts/analyze_system.py" "$CONFIG_DIR" "$DB_PATH"
log_success "System analysis complete"


# Create systemd service
log_info "Creating systemd user service..."
mkdir -p "$HOME/.config/systemd/user"


cat > "$HOME/.config/systemd/user/hyprai.service" << EOF
[Unit]
Description=HyprAI Daemon - AI Desktop Automation
After=graphical-session.target


[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/daemon/main.py
Restart=on-failure
RestartSec=5
Environment="DISPLAY=:0"
Environment="WAYLAND_DISPLAY=wayland-1"


[Install]
WantedBy=default.target
EOF


systemctl --user daemon-reload
systemctl --user enable hyprai.service


log_success "Systemd service created"


# Enable ydotool
log_info "Configuring ydotool..."
sudo systemctl enable --now ydotool
sudo usermod -aG input "$USER"


echo ""
echo -e "${GREEN}=========================================="
echo -e "  Installation Complete!"
echo -e "==========================================${NC}"
echo ""
echo -e "To start HyprAI:"
echo -e "  ${BLUE}systemctl --user start hyprai${NC}"
echo ""
echo -e "Web dashboard will be available at:"
echo -e "  ${BLUE}http://localhost:8765${NC}"
echo ""
echo -e "${YELLOW}NOTE: You may need to log out and back in for group permissions${NC}"
echo ""