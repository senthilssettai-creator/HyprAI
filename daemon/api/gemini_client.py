"""Gemini client adapter - Phase 0 stub.

This module provides a simple offline stub that echoes prompts back as a 'plan'.
When you're ready to wire in a real Gemini API, add the official SDK calls
and ensure the API key is stored safely and not logged.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("GeminiClient")


class GeminiClient:
    def __init__(self, config):
        self.config = config
        self.model = self.config.get("api", "model", fallback="stub")
        # Do NOT auto-initialize remote SDK in Phase 0. User must opt-in later.

    async def process_query(self, query: str, context: Dict[str, Any], has_screenshot: bool = False) -> Dict[str, Any]:
        """Return a simple local 'plan' for testing and developer convenience."""
        logger.info("GeminiClient (stub) processing query")
        # Very small 'plan' structure used by dispatcher
        return {
            "actions": [
                {"type": "response", "params": {"text": f"Echo: {query}"}}
            ],
            "explanation": "Local stub response (no external API called)."
        }
