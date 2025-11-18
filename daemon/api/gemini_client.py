"""
REAL GEMINI CLIENT (Google Generative AI)
Fully integrated for HyprAI.

Supports:
- Text + image input
- Real JSON action plan extraction
- Uses API key from config.ini
"""

import logging
import base64
import google.generativeai as genai

logger = logging.getLogger("GeminiClient")


class GeminiClient:
    def __init__(self, config):
        self.config = config

        if not config.api_key:
            raise ValueError("No API key found in config.ini")

        # Configure SDK
        genai.configure(api_key=config.api_key)

        model_name = config.model or "gemini-1.5-flash"
        logger.info(f"Using Gemini model: {model_name}")

        # Load model
        self.model = genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": 0.1,
                "top_p": 1,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            }
        )

    async def process_query(self, query: str, context: dict, include_screenshot: bool):
        """
        Build the real Gemini prompt & return an AI-generated action plan.
        """

        logger.info("Sending request to Gemini…")

        # Build system prompt
        sys_prompt = self._build_system_prompt()

        # Convert screenshot if present
        parts = [
            sys_prompt,
            "\nUSER QUERY:\n" + query,
            "\nFULL CONTEXT:\n" + str(context),
        ]

        images = []
        if include_screenshot and "screenshot" in context:
            try:
                img_bytes = base64.b64decode(context["screenshot"])
                images.append({"mime_type": "image/png", "data": img_bytes})
            except Exception:
                logger.warning("Screenshot decode failed")

        try:
            # Gemini accepts mixed input: text + images
            response = self.model.generate_content(
                parts + images
            )

            text = response.text
            logger.info("Gemini raw output: %s", text)

            # Expect JSON — if not JSON, wrap fallback
            import json
            try:
                return json.loads(text)
            except Exception:
                logger.warning("Model returned non-JSON, wrapping")
                return {
                    "actions": [
                        {"type": "response", "params": {"text": text}}
                    ]
                }

        except Exception as e:
            logger.exception("Gemini request failed")
            return {
                "actions": [
                    {"type": "response", "params": {"text": f"Gemini error: {e}"}}
                ]
            }

    def _build_system_prompt(self):
        """
        Tells Gemini EXACTLY how to respond.
        """
        return """
You are HyprAI — a real system automation AI running locally on Arch Linux with Hyprland.

Your job is to output ONLY a JSON object describing an action plan.
Never output plain text. Never explain. Only JSON.

ACTION FORMAT:
{
  "actions": [
    {
      "type": "<action_type>",
      "params": { ... }
    }
  ]
}

Allowed action types:
- keyboard
- mouse
- shell
- hyprctl
- window
- screenshot
- file
- response

If unsure what to do:
Return a single "response" action.

NEVER include commentary outside JSON.
"""

