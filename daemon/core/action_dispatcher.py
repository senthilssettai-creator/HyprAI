"""Action dispatcher - uses Wayland-friendly tools (wlrctl / wtype) when possible."""

import asyncio
import subprocess
import logging
import json
from typing import Dict, Any

logger = logging.getLogger("ActionDispatcher")


class ActionDispatcher:
    def __init__(self, config, context):
        self.config = config
        self.context = context
        # detect available tools
        self.has_wlrctl = self._which("wlrctl")
        self.has_wtype = self._which("wtype")
        self.has_grim = self._which("grim")
        self.has_slurp = self._which("slurp")

    def _which(self, cmd: str) -> bool:
        from shutil import which
        return which(cmd) is not None

    async def execute_action_plan(self, plan: Dict[str, Any]):
        """Execute plan — plan is dict with 'actions' list or a string."""
        if isinstance(plan, str):
            # treat as shell command
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
        params = action.get("params", {})
        handlers = {
            "keyboard": self.keyboard_input,
            "mouse": self.mouse_action,
            "shell": self.shell_exec,
            "hyprctl": self.hyprctl_command,
            "window": self.window_control,
            "screenshot": self.take_screenshot,
            "file": self.file_operation,
        }
        handler = handlers.get(t)
        if not handler:
            return {"error": f"unknown action type: {t}"}
        try:
            result = await handler(**params)
            await self.context.store_command(str(action), str(result), True)
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception("Action failed")
            await self.context.store_command(str(action), str(e), False)
            return {"success": False, "error": str(e)}

    async def keyboard_input(self, keys: str = None, text: str = None, **kwargs):
        """Use wtype to type text or emulate keys. Falls back to printing."""
        if text:
            if self.has_wtype:
                cmd = ["wtype", text]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
            else:
                # fallback: echo into focused terminal (very limited)
                logger.warning("wtype not available; writing to stdout as fallback")
                return {"dry_run": True, "text": text}
        if keys:
            # wtype doesn't support complex key combos easily; attempt simple mapping
            if self.has_wtype:
                seq = keys.replace("+", " ")
                cmd = ["wtype", seq]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
            else:
                return {"error": "no wtype installed to emit keys"}
        return {"error": "no keys or text provided"}

    async def mouse_action(self, action="move", x=0, y=0, button=1, **kwargs):
        """Mouse control: best-effort using wlrctl if available."""
        if not self._which("wlrctl"):
            return {"error": "no wlrctl installed for mouse control"}
        if action == "move":
            cmd = ["wlrctl", "cursor", "warp", str(x), str(y)]
        elif action == "click":
            cmd = ["wlrctl", "pointer", "button", str(button), "press"]
        else:
            return {"error": f"unknown mouse action {action}"}
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}

    async def shell_exec(self, command: str, timeout: int = 30, **kwargs):
        """Execute shell command if allowed by config."""
        if not self.config.get_bool("automation", "enable_shell", fallback=False):
            return {"error": "shell execution disabled"}
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {"returncode": proc.returncode, "stdout": out.decode(), "stderr": err.decode()}
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": "timeout"}

    async def hyprctl_command(self, command: str, **kwargs):
        """Run hyprctl - pass through."""
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
        """Use grim (+slurp) to produce PNG; return bytes length or base64 if needed."""
        if not self.has_grim:
            return {"error": "grim not available"}
        if region:
            cmd = ["grim", "-g", region, "-"]
        else:
            cmd = ["grim", "-"]
        proc = subprocess.run(cmd, capture_output=True)
        return {"size": len(proc.stdout), "rc": proc.returncode}

    async def file_operation(self, operation: str, path: str, content: str = None, **kwargs):
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
        return {"error": "unknown file op"}
