#!/usr/bin/env python3
"""
HyprAI Main Daemon
Orchestrates all system monitoring, AI processing, and action execution
"""


import asyncio
import logging
import signal
import sys
from pathlib import Path


from core.config_manager import ConfigManager
from core.context_engine import ContextEngine
from core.hyprland_monitor import HyprlandMonitor
from core.action_dispatcher import ActionDispatcher
from api.gemini_client import GeminiClient
from api.web_server import WebServer


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.local/share/hyprai/logs/daemon.log'),
        logging.StreamHandler()
    ]
)


logger = logging.getLogger('HyprAI')


class HyprAIDaemon:
    def __init__(self):
        self.config = ConfigManager()
        self.context = ContextEngine(self.config)
        self.hyprland = HyprlandMonitor(self.context)
        self.dispatcher = ActionDispatcher(self.config, self.context)
        self.gemini = GeminiClient(self.config)
        self.web_server = WebServer(self.config, self)
        
        self.running = False
        
    async def start(self):
        """Start all daemon components"""
        logger.info("Starting HyprAI Daemon...")
        self.running = True
        
        # Initialize context with system state
        await self.context.initialize()
        
        # Start Hyprland event monitoring
        asyncio.create_task(self.hyprland.monitor_events())
        
        # Start web server
        asyncio.create_task(self.web_server.start())
        
        logger.info("HyprAI Daemon running. Web interface: http://localhost:8765")
        
        # Keep daemon alive
        while self.running:
            await asyncio.sleep(1)
    
    async def process_user_query(self, query: str, include_screenshot: bool = False):
        """Process user query with full context"""
        try:
            # Build comprehensive context
            context = await self.context.build_full_context(include_screenshot)
            
            # Send to Gemini with vision if screenshot included
            response = await self.gemini.process_query(query, context, include_screenshot)
            
            # Execute actions from response
            results = await self.dispatcher.execute_action_plan(response)
            
            # Store conversation
            await self.context.store_conversation(query, response, results)
            
            return {
                'success': True,
                'response': response,
                'actions_executed': results
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {'success': False, 'error': str(e)}
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down HyprAI Daemon...")
        self.running = False
        await self.web_server.stop()
        await self.context.close()


def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}")
    sys.exit(0)


async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    daemon = HyprAIDaemon()
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await daemon.shutdown()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())