"""
Context Engine - Builds and stores system context
"""

import asyncio
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
import logging
import shutil

logger = logging.getLogger("ContextEngine")


class ContextEngine:
    def __init__(self, config):
        """
        config: ConfigManager instance (must expose .db_path attribute)
        """
        self.config = config
        self.db_path = str(Path(self.config.db_path).expanduser())
        self.conn = None
        self.hypr_config = {}
        self.dotfiles = {}

    async def initialize(self):
        """Open DB and perform lightweight initial analysis."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # Initialize sqlite
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            output TEXT,
            success INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            ai_response TEXT,
            context TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT,
            pattern_data TEXT,
            frequency INTEGER DEFAULT 1,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        self.conn.commit()

        # quick analyses
        await self._analyze_hyprland_conf()
        await self._analyze_dotfiles()
        await self._update_system_state()

    async def _analyze_hyprland_conf(self):
        config_path = Path.home() / ".config" / "hypr" / "hyprland.conf"
        if not config_path.exists():
            logger.debug("Hyprland config not found")
            return
        try:
            text = config_path.read_text(errors="ignore")
            keybinds = [line.strip() for line in text.splitlines() if "bind" in line and "=" in line]
            self.hypr_config["keybinds"] = keybinds
            # store small snapshot
            self._upsert_system_state("hyprland_config", json.dumps({"keybinds": keybinds}))
            logger.info("Parsed Hyprland config (keybinds=%d)", len(keybinds))
        except Exception as e:
            logger.exception("Failed parsing hyprland conf: %s", e)

    async def _analyze_dotfiles(self):
        home = Path.home()
        candidates = [
            home / ".bashrc",
            home / ".zshrc",
            home / ".config" / "nvim" / "init.lua",
            home / ".config" / "waybar" / "config",
        ]
        found = {}
        for p in candidates:
            if p.exists():
                try:
                    found[str(p)] = p.read_text(encoding="utf-8", errors="ignore")[:5000]
                except Exception:
                    found[str(p)] = "<read-error>"
        self.dotfiles = found
        self._upsert_system_state("dotfiles_snapshot", json.dumps({"files": list(found.keys())}))

    async def _update_system_state(self):
        """Collect basic hyprctl state if available."""
        state = {}
        hyprctl = shutil.which("hyprctl")
        if hyprctl:
            try:
                out = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=2)
                state["monitors"] = json.loads(out.stdout) if out.stdout else {}
            except Exception:
                state["monitors"] = {}
            try:
                out = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=2)
                state["active_window"] = json.loads(out.stdout) if out.stdout else {}
            except Exception:
                state["active_window"] = {}
            try:
                out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2)
                state["clients"] = json.loads(out.stdout) if out.stdout else []
            except Exception:
                state["clients"] = []
        else:
            logger.debug("hyprctl not available on PATH")

        self._upsert_system_state("current_state", json.dumps(state))
        return state

    async def build_full_context(self, include_screenshot=False):
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_state": await self._async_wrap(self._update_system_state),
            "hyprland_config": self.hypr_config,
            "recent_commands": self._get_recent_commands(10),
            "conversation_history": self._get_recent_conversations(5),
            "dotfiles": list(self.dotfiles.keys()),
        }
        if include_screenshot:
            ss = await self._async_wrap(self._take_screenshot)
            context["screenshot"] = ss
        return context

    async def _take_screenshot(self):
        import base64
        from io import BytesIO
        from PIL import Image  # pillow in venv
        import subprocess
        try:
            proc = subprocess.run(["grim", "-"], capture_output=True, timeout=5)
            if proc.returncode != 0:
                return None
            data = proc.stdout
            return base64.b64encode(data).decode()
        except Exception as e:
            logger.exception("Screenshot failed: %s", e)
            return None

    def _get_recent_commands(self, limit=10):
        cur = self.conn.cursor()
        cur.execute("SELECT command, output, success FROM command_history ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [{"cmd": r[0], "output": r[1], "success": bool(r[2])} for r in cur.fetchall()]

    def _get_recent_conversations(self, limit=5):
        cur = self.conn.cursor()
        cur.execute("SELECT user_message, ai_response FROM conversations ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [{"user": r[0], "ai": r[1]} for r in cur.fetchall()]

    async def store_conversation(self, user_msg, ai_response, context):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO conversations (user_message, ai_response, context) VALUES (?, ?, ?)",
                    (user_msg, str(ai_response), json.dumps(context)))
        self.conn.commit()

    async def store_command(self, command, output, success):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO command_history (command, output, success) VALUES (?, ?, ?)",
                    (command, str(output), 1 if success else 0))
        self.conn.commit()

    def _upsert_system_state(self, key, value):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, value))
        self.conn.commit()

    async def _async_wrap(self, fn, *a, **kw):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: asyncio.run(fn(*a, **kw)) if asyncio.iscoroutinefunction(fn) else fn(*a, **kw))
