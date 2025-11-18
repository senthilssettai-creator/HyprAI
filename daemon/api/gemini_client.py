"""Gemini API client with vision support"""
import google.generativeai as genai
import logging
import json


logger = logging.getLogger('GeminiClient')


class GeminiClient:
    def __init__(self, config):
        self.config = config
        genai.configure(api_key=config.gemini_key)
        self.model = genai.GenerativeModel(config.model)
        
        self.system_prompt = """You are HyprAI, an advanced AI assistant with complete control over an Arch Linux system running Hyprland.


You have access to:
- Full system state (windows, workspaces, processes)
- User's Hyprland configuration and keybindings
- Command history and patterns
- Visual screen content (when screenshot provided)
- Complete dotfile configurations


You can execute actions via a JSON action plan format:
{
  "actions": [
    {
      "type": "keyboard|mouse|shell|hyprctl|window|screenshot|file",
      "params": {...}
    }
  ],
  "explanation": "What you're doing and why"
}


Available action types:
- keyboard: {keys: "super+shift+return"} or {text: "hello world"}
- mouse: {action: "move|click|scroll", x: 100, y: 200, button: 1}
- shell: {command: "ls -la"}
- hyprctl: {command: "dispatch workspace 2"}
- window: {action: "focus|close|fullscreen|move", target: "kitty"}
- screenshot: {region: "x,y WxH"}
- file: {operation: "read|write|append", path: "~/file.txt", content: "..."}


When analyzing screenshots, describe what you see and suggest relevant actions.
Be proactive, intelligent, and execute complex multi-step operations seamlessly.
"""
    
    async def process_query(self, query, context, has_screenshot=False):
        """Process user query with full context"""
        
        # Build context message
        context_msg = f"""
CURRENT SYSTEM STATE:
{json.dumps(context.get('system_state', {}), indent=2)}


RECENT COMMANDS:
{json.dumps(context.get('recent_commands', []), indent=2)}


HYPRLAND CONFIG (keybindings):
{json.dumps(context.get('hyprland_config', {}).get('keybinds', [])[:20], indent=2)}


USER QUERY: {query}
"""
        
        try:
            if has_screenshot and context.get('screenshot'):
                # Vision-enabled request
                import PIL.Image
                import io
                import base64
                
                img_data = base64.b64decode(context['screenshot'])
                img = PIL.Image.open(io.BytesIO(img_data))
                
                response = self.model.generate_content([
                    self.system_prompt,
                    context_msg,
                    "SCREENSHOT OF CURRENT SCREEN:",
                    img
                ])
            else:
                # Text-only request
                response = self.model.generate_content([
                    self.system_prompt,
                    context_msg
                ])
            
            # Try to extract JSON action plan
            text = response.text
            
            # Look for JSON in response
            if '{' in text and '}' in text:
                start = text.find('{')
                end = text.rfind('}') + 1
                json_str = text[start:end]
                try:
                    action_plan = json.loads(json_str)
                    return action_plan
                except json.JSONDecodeError:
                    pass
            
            # If no JSON, return as text response
            return {
                'actions': [{'type': 'response', 'params': {'text': text}}],
                'explanation': text
            }
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                'actions': [],
                'explanation': f'Error: {str(e)}'
            }