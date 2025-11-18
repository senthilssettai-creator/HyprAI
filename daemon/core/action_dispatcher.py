"""Action dispatcher - Wayland-friendly"""

import asyncio
import subprocess
import logging
import json
from typing import Dict, Any
from shutil import which

logger = logging.getLogger("ActionDispatcher")


class ActionDispatcher:
    def __init__(self, config, context):
        self.config = config
        self.context = context
        self.has_wtype = which("wtype") is not None
        self.has_wlrctl = which("wlrctl") is not None
        self.has_grim = which("grim") is not None

    async def execute_action_plan(self, plan: Dict[str, Any]):
        if isinstance(plan, str):
            return [await self.shell_exec(plan)]
        if not isinstance(plan, dict) or "actions" not in plan:
            return {"error": "invalid plan format"}
        results = []
        for action in plan["actions"]:
            res = await self._execute_single_action(action)
            results.append(res)
        return results

    async def _execute_single_action(self, action: Dict[str, Any]):
        t = action.get("type")
        params = action.get("params", {}) or {}
        handlers = {
            "keyboard": self.keyboard_input,
            "mouse": self.mouse_action,
            "shell": self.shell_exec,
            "hyprctl": self.hyprctl_command,
            "window": self.window_control,
            "screenshot": self.take_screenshot,
            "file": self.file_operation,
            "response": self._response_action,
        }
        handler = handlers.get(t)
        if not handler:
            return {"error": f"unknown action type: {t}"}
        try:
            result = await handler(**params)
            # store executed command in DB
            try:
                await self.context.store_command(str(action), str(result), True)
            except Exception:
                logger.debug("Failed to store command")
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception("Action failed")
            try:
                await self.context.store_command(str(action), str(e), False)
            except Exception:
                pass
            return {"success": False, "error": str(e)}

    # simple response action (no-op)
    async def _response_action(self, text=None, **kwargs):
        return {"text": text}

    async def keyboard_input(self, keys: str = None, text: str = None, **kwargs):
        if text:
            if self.has_wtype:
                proc = subprocess.run(["wtype", text], capture_output=True, text=True)
                return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
            else:
                return {"error": "wtype not installed"}
        if keys:
            if self.has_wtype:
                seq = keys.replace("+", " ")
                proc = subprocess.run(["wtype", seq], capture_output=True, text=True)
                return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
            else:
                return {"error": "wtype not installed"}
        return {"error": "no keys/text provided"}

    async def mouse_action(self, action="move", x=0, y=0, button=1, **kwargs):
        if not self.has_wlrctl:
            return {"error": "wlrctl not installed"}
        if action == "move":
            proc = subprocess.run(["wlrctl", "cursor", "warp", str(x), str(y)], capture_output=True, text=True)
            return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
        if action == "click":
            proc = subprocess.run(["wlrctl", "pointer", "button", str(button), "press"], capture_output=True, text=True)
            return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
        return {"error": f"unknown mouse action {action}"}

    async def shell_exec(self, command: str, timeout: int = 30, **kwargs):
        if not getattr(self.config, "enable_shell_exec", False):
            return {"error": "shell execution disabled in config"}
        proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {"returncode": proc.returncode, "stdout": out.decode(), "stderr": err.decode()}
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": "timeout"}

    async def hyprctl_command(self, command: str, **kwargs):
        proc = subprocess.run(["hyprctl"] + command.split(), capture_output=True, text=True)
        return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}

    async def window_control(self, action: str, target: str = None, **kwargs):
        mapping = {
            "focus": f"dispatch focuswindow {target}",
            "close": f"dispatch closewindow {target}",
            "fullscreen": "dispatch fullscreen",
        }
        cmd = mapping.get(action)
        if not cmd:
            return {"error": f"unsupported window action {action}"}
        return await self.hyprctl_command(cmd)

    async def take_screenshot(self, region: str = None, **kwargs):
        if not self.has_grim:
            return {"error": "grim not installed"}
        if region:
            proc = subprocess.run(["grim", "-g", region, "-"], capture_output=True)
        else:
            proc = subprocess.run(["grim", "-"], capture_output=True)
        return {"size": len(proc.stdout), "rc": proc.returncode}

    async def file_operation(self, operation: str, path: str, content: str = None, **kwargs):
        if not getattr(self.config, "enable_file_ops", False):
            return {"error": "file operations disabled"}
        from pathlib import Path
        p = Path(path).expanduser()
        if operation == "read":
            return {"content": p.read_text()}
        if operation == "write":
            p.write_text(content or "")
            return {"success": True}
        if operation == "append":
            with p.open("a") as fh:
                fh.write(content or "")
            return {"success": True}
        return {"error": "unknown file operation"}

