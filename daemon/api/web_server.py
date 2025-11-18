"""FastAPI web server for HyprAI dashboard."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logger = logging.getLogger("WebServer")


class WebServer:
    def __init__(self, config, daemon):
        """
        config: ConfigManager
        daemon: HyprAIDaemon instance
        """
        self.config = config
        self.daemon = daemon
        self.app = FastAPI()
        # Determine web static directory relative to repo root (two parents up from this file)
        repo_root = Path(__file__).resolve().parents[2]
        web_dir = repo_root / "web"
        if not web_dir.exists():
            # fallback to CWD/web
            web_dir = Path.cwd() / "web"
        self.web_dir = web_dir
        logger.info("Web static dir: %s", str(self.web_dir))
        self.app.mount("/", StaticFiles(directory=str(self.web_dir), html=True), name="web")
        self._setup_routes()
        self._server = None

    def _setup_routes(self):
        @self.app.get("/api/status")
        async def status():
            try:
                state = await self.daemon.context._update_system_state()
                return JSONResponse({"status": "running", "system_state": state})
            except Exception as e:
                logger.exception("status error")
                return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

        @self.app.post("/api/query")
        async def query(req: Request):
            payload = await req.json()
            q = payload.get("query")
            include_screenshot = payload.get("screenshot", False)
            if not q:
                return JSONResponse({"error": "no query"}, status_code=400)
            res = await self.daemon.process_user_query(q, include_screenshot)
            return JSONResponse(res)

    async def start(self):
        port = int(self.config.port or 8765)
        config = uvicorn.Config(self.app, host="127.0.0.1", port=port, log_level="info")
        server = uvicorn.Server(config)
        loop = asyncio.get_event_loop()
        # run uvicorn in thread to not block the event loop
        await loop.run_in_executor(None, server.run)
        self._server = server

    async def stop(self):
        # uvicorn.Server.run sets server.should_exit when stopped; however here we simply log
        logger.info("Stopping webserver (no-op)")

