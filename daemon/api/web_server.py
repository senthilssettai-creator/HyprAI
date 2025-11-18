"""FastAPI web server for HyprAI dashboard."""

import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional

logger = logging.getLogger("WebServer")


class WebServer:
    def __init__(self, config, daemon):
        self.config = config
        self.daemon = daemon
        self.app = FastAPI()
        # mount static web folder (relative to project install path)
        # The installation copies `web/` under the install dir, and systemd's working dir is the home
        self.app.mount("/", StaticFiles(directory=str(config.get("system", "web_dir", fallback="web")), html=True), name="web")
        self._setup_routes()
        self._server = None

    def _setup_routes(self):
        @self.app.get("/api/status")
        async def status():
            state = await self.daemon.context._update_system_state()
            return JSONResponse({"status": "running", "system_state": state})

        @self.app.post("/api/query")
        async def query(req: Request):
            body = await req.json()
            q = body.get("query")
            include_screenshot = body.get("screenshot", False)
            if not q:
                return JSONResponse({"error": "no query provided"}, status_code=400)
            res = await self.daemon.process_user_query(q, include_screenshot)
            return JSONResponse(res)

    async def start(self):
        # Run uvicorn in background thread
        self._server = uvicorn.Server(
            config=uvicorn.Config(self.app, host="127.0.0.1", port=int(self.config.get("system", "port", fallback=8765)), log_level="info")
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._server.run)

    async def stop(self):
        if self._server:
            self._server.should_exit = True
            logger.info("Web server stopping")
