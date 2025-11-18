"""
Context Engine - Builds comprehensive system understanding
"""
import asyncio
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
import logging


logger = logging.getLogger('ContextEngine')


class ContextEngine:
    def __init__(self, config):
        self.config = config
        self.db_path = config.db_path
        self.conn = None
        self.hypr_config = {}
        self.dotfiles = {}
        
    async def initialize(self):
        """Initialize context database and perform system analysis"""
        self.conn = sqlite3.connect(self.db_path)
        await self._analyze_hyprland_config()
        await self._analyze_dotfiles()
        await self._update_system_state()
    
    async def _analyze_hyprland_config(self):
        """Parse Hyprland configuration"""
        config_path = Path.home() / '.config/hypr/hyprland.conf'
        if not config_path.exists():
            return
        
        with open(config_path) as f:
            content = f.read()
        
        # Parse keybindings
        keybinds = []
        for line in content.split('\n'):
            if 'bind' in line and '=' in line:
                keybinds.append(line.strip())
        
        self.hypr_config['keybinds'] = keybinds
        
        # Store in database
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO system_state VALUES (?, ?, ?)",
                  ('hyprland_config', json.dumps(self.hypr_config), datetime.now()))
        self.conn.commit()
        
        logger.info(f"Parsed {len(keybinds)} Hyprland keybindings")
    
    async def _analyze_dotfiles(self):
        """Analyze user dotfiles"""
        config_dir = Path.home() / '.config'
        
        # Common dotfile locations
        dotfile_paths = [
            Path.home() / '.bashrc',
            Path.home() / '.zshrc',
            config_dir / 'nvim/init.lua',
            config_dir / 'waybar/config',
        ]
        
        for path in dotfile_paths:
            if path.exists():
                self.dotfiles[str(path)] = path.read_text()[:5000]  # First 5KB
        
        logger.info(f"Analyzed {len(self.dotfiles)} dotfiles")
    
    async def _update_system_state(self):
        """Update current system state"""
        state = {}
        
        try:
            # Hyprland monitors
            result = subprocess.run(['hyprctl', 'monitors', '-j'], 
                                    capture_output=True, text=True)
            state['monitors'] = json.loads(result.stdout)
            
            # Active window
            result = subprocess.run(['hyprctl', 'activewindow', '-j'],
                                    capture_output=True, text=True)
            state['active_window'] = json.loads(result.stdout)
            
            # All clients
            result = subprocess.run(['hyprctl', 'clients', '-j'],
                                    capture_output=True, text=True)
            state['clients'] = json.loads(result.stdout)
            
        except Exception as e:
            logger.error(f"Error updating system state: {e}")
        
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO system_state VALUES (?, ?, ?)",
                  ('current_state', json.dumps(state), datetime.now()))
        self.conn.commit()
        
        return state
    
    async def build_full_context(self, include_screenshot=False):
        """Build comprehensive context for AI"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'system_state': await self._update_system_state(),
            'hyprland_config': self.hypr_config,
            'recent_commands': self._get_recent_commands(10),
            'conversation_history': self._get_recent_conversations(5),
        }
        
        if include_screenshot:
            context['screenshot'] = await self._take_screenshot()
        
        return context
    
    async def _take_screenshot(self):
        """Take screenshot and return base64"""
        import base64
        from io import BytesIO
        from PIL import Image
        
        try:
            result = subprocess.run(['grim', '-'], capture_output=True)
            img = Image.open(BytesIO(result.stdout))
            
            # Resize for API efficiency
            img.thumbnail((1024, 1024))
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    def _get_recent_commands(self, limit=10):
        """Get recent command history"""
        c = self.conn.cursor()
        c.execute("SELECT command, output, success FROM command_history ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [{'cmd': row[0], 'output': row[1], 'success': bool(row[2])} for row in c.fetchall()]
    
    def _get_recent_conversations(self, limit=5):
        """Get recent conversation history"""
        c = self.conn.cursor()
        c.execute("SELECT user_message, ai_response FROM conversations ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [{'user': row[0], 'ai': row[1]} for row in c.fetchall()]
    
    async def store_conversation(self, user_msg, ai_response, context):
        """Store conversation in database"""
        c = self.conn.cursor()
        c.execute("INSERT INTO conversations (user_message, ai_response, context) VALUES (?, ?, ?)",
                  (user_msg, str(ai_response), json.dumps(context)))
        self.conn.commit()
    
    async def store_command(self, command, output, success):
        """Store command execution"""
        c = self.conn.cursor()
        c.execute("INSERT INTO command_history (command, output, success) VALUES (?, ?, ?)",
                  (command, output, 1 if success else 0))
        self.conn.commit()
    
    async def close(self):
        if self.conn:
            self.conn.close()