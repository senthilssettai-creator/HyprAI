#!/usr/bin/env python3
"""
HyprAI Main Daemon
Orchestrates system monitoring, web server and AI glue.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from core.config_manager import ConfigManager
from core.context_engine import ContextEngine
from core.hyprland_monitor import HyprlandMonitor
from core.action_dispatcher import ActionDispatcher
from api.gemini_client import GeminiClient
from api.web_server import WebServer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
                    handlers=[logging.StreamHandler()])

logger = logging.getLogger("HyprAI")


class HyprAIDaemon:
    def __init__(self):
        self.config = ConfigManager()
        self.context = ContextEngine(self.config)
        self.hyprland = HyprlandMonitor(self.context)
        self.dispatcher = ActionDispatcher(self.config, self.context)
        self.gemini = GeminiClient(self.config)
        self.web_server = WebServer(self.config, self)
        self.running = False
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def start(self):
        logger.info("Starting HyprAI daemon")
        self.running = True

        # Ensure DB and context initialized
        await self.context.initialize()

        # start hyprland socket monitor (non-blocking)
        asyncio.create_task(self.hyprland.monitor_events())

        # start web server (uvicorn in thread)
        await self.web_server.start()

        # Keep the daemon alive
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            await self.shutdown()

    async def process_user_query(self, query: str, include_screenshot: bool = False):
        # Build context and send to Gemini (stub) adapter
        try:
            context = await self.context.build_full_context(include_screenshot)
            response = await self.gemini.process_query(query, context, include_screenshot)
            results = await self.dispatcher.execute_action_plan(response)
            await self.context.store_conversation(query, str(response), results)
            return {"success": True, "response": response, "actions_executed": results}
        except Exception as e:
            logger.exception("Error processing query")
            return {"success": False, "error": str(e)}

    async def shutdown(self):
        if not self.running:
            return
        logger.info("Shutting down HyprAI daemon")
        self.running = False
        await self.web_server.stop()
        await self.context.close()
        self._executor.shutdown(wait=False)


def signal_handler(signum, frame):
    logger.info("Signal received, shutting down...")
    sys.exit(0)


async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    daemon = HyprAIDaemon()
    try:
        await daemon.start()
    except Exception:
        logger.exception("Fatal error in daemon")
        await daemon.shutdown()
        raise


if __name__ == "__main__":
    asyncio.run(main())
