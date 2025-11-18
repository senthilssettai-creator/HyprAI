# HyprAI 🤖


**Advanced AI Desktop Automation Suite for Arch Linux + Hyprland**


HyprAI is a sophisticated AI assistant that has complete awareness and control over your Hyprland desktop environment. It can see your screen, understand your configuration, and execute complex automation tasks through natural language.


## Features


- 🧠 **Context-Aware AI**: Understands your entire system configuration, keybindings, and workflow
- 👁️ **Vision Capabilities**: Can analyze screenshots of your desktop using Gemini's multimodal AI
- ⌨️ **Complete Control**: Keyboard input, mouse control, window management, shell commands
- 🔍 **Self-Learning**: Builds a knowledge graph of your habits and frequently used commands
- 🌐 **Web Dashboard**: Beautiful interface for chatting with your AI assistant
- 🔒 **Privacy-Focused**: All data stored locally, API key encrypted
- ⚡ **Hyprland Native**: Deep integration with Hyprland's IPC system


## Installation


### Prerequisites
- Arch Linux
- Hyprland Wayland compositor
- Google Gemini API key (free tier available at https://makersuite.google.com/app/apikey)


### Quick Start


```bash
# Clone or download this repository
git clone <your-repo-url> HyprAI
cd HyprAI


# Run the installer
chmod +x install.sh
./install.sh


# Follow the prompts to enter your Gemini API key
```


The installer will:
1. Check and install all dependencies
2. Analyze your Hyprland configuration
3. Set up the AI daemon as a systemd service
4. Create a local database for context storage


### Starting HyprAI


```bash
# Start the service
systemctl --user start hyprai


# View logs
journalctl --user -u hyprai -f


# Access web dashboard
firefox http://localhost:8765
```


## Usage


Open the web dashboard and try commands like:


- "Take a screenshot and tell me what's on my screen"
- "Open Firefox on workspace 2 and navigate to GitHub"
- "What windows do I currently have open?"
- "Run my deploy script in a new terminal"
- "Focus my Neovim window"
- "Execute my custom workflow: open VS Code, terminal, and browser"


### Vision Mode


Check "Include Screenshot" to let the AI see your screen and provide visual context-aware responses.


## Architecture


- **Daemon** (`daemon/`): Core Python service that monitors Hyprland events
- **Context Engine**: Builds comprehensive understanding of your system
- **Action Dispatcher**: Executes commands via ydotool, hyprctl, and shell
- **Gemini Client**: Interfaces with Google's AI API
- **Web Server**: Flask-based dashboard for user interaction


## Configuration


Configuration file: `~/.config/hyprai/config.ini`


```ini
[api]
gemini_key = your_api_key_here
model = gemini-1.5-flash


[security]
enable_file_ops = true
enable_shell_exec = true
```


## Security


- API key stored with 600 permissions
- Optional sandboxing for file and shell operations
- All data remains local on your machine
- No telemetry or external data transmission


## Dependencies


- Python 3.11+
- ydotool (Wayland input synthesis)
- grim, slurp (screenshots)
- hyprctl (Hyprland control)
- google-generativeai (Gemini API)
- Flask (web interface)


## Troubleshooting


**Service won't start:**
```bash
systemctl --user status hyprai
journalctl --user -u hyprai -n 50
```


**ydotool not working:**
```bash
sudo systemctl status ydotool
sudo usermod -aG input $USER
# Log out and back in
```


**Web dashboard inaccessible:**
Check if port 8765 is available:
```bash
ss -tlnp | grep 8765
```


## Contributing


This is a foundation for an incredibly powerful system. Contributions welcome for:
- Additional action types
- More sophisticated context analysis
- UI improvements
- Integration with more dotfile managers


## License


MIT License - See LICENSE file


## Credits


Built with ❤️ for the Hyprland community
Powered by Google Gemini AI