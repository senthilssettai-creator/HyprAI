"""Hyprland event monitoring via socket"""
import asyncio
import json
import logging
import os


logger = logging.getLogger('HyprlandMonitor')


class HyprlandMonitor:
    def __init__(self, context):
        self.context = context
        self.signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
        
    async def monitor_events(self):
        """Monitor Hyprland events via socket"""
        if not self.signature:
            logger.warning("Not running under Hyprland, event monitoring disabled")
            return
        
        socket_path = f"/tmp/hypr/{self.signature}/.socket2.sock"
        
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(socket_path)
                logger.info("Connected to Hyprland event socket")
                
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    
                    event = data.decode().strip()
                    await self._handle_event(event)
                    
            except Exception as e:
                logger.error(f"Event monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_event(self, event):
        """Process Hyprland events"""
        # Events format: "EVENT>>DATA"
        if '>>' in event:
            event_type, data = event.split('>>', 1)
            logger.debug(f"Event: {event_type} - {data}")
            
            # Update context based on event
            if event_type in ['activewindow', 'workspace', 'focusedmon']:
                await self.context._update_system_state()