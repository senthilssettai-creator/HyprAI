"""Execute actions on the system"""
import asyncio
import subprocess
import logging
import json


logger = logging.getLogger('ActionDispatcher')


class ActionDispatcher:
    def __init__(self, config, context):
        self.config = config
        self.context = context
    
    async def execute_action_plan(self, plan):
        """Execute a plan of actions from AI"""
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except:
                # If AI returned text instead of JSON, treat as shell command
                return await self.shell_exec(plan)
        
        if not isinstance(plan, dict) or 'actions' not in plan:
            return {'error': 'Invalid action plan format'}
        
        results = []
        for action in plan['actions']:
            result = await self._execute_single_action(action)
            results.append(result)
        
        return results
    
    async def _execute_single_action(self, action):
        """Execute a single action"""
        action_type = action.get('type')
        params = action.get('params', {})
        
        handlers = {
            'keyboard': self.keyboard_input,
            'mouse': self.mouse_action,
            'shell': self.shell_exec,
            'hyprctl': self.hyprctl_command,
            'window': self.window_control,
            'screenshot': self.take_screenshot,
            'file': self.file_operation,
        }
        
        handler = handlers.get(action_type)
        if not handler:
            return {'error': f'Unknown action type: {action_type}'}
        
        try:
            result = await handler(**params)
            await self.context.store_command(str(action), str(result), True)
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Action failed: {e}")
            await self.context.store_command(str(action), str(e), False)
            return {'success': False, 'error': str(e)}
    
    async def keyboard_input(self, keys=None, text=None, **kwargs):
        """Simulate keyboard input"""
        if text:
            cmd = ['ydotool', 'type', text]
        elif keys:
            # Parse key combinations like "super+shift+return"
            key_codes = self._parse_keys(keys)
            cmd = ['ydotool', 'key'] + key_codes
        else:
            return {'error': 'No keys or text provided'}
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {'stdout': result.stdout, 'stderr': result.stderr}
    
    def _parse_keys(self, keys):
        """Convert key names to ydotool codes"""
        # Simplified key mapping
        key_map = {
            'super': '125:1', 'ctrl': '29:1', 'shift': '42:1', 'alt': '56:1',
            'return': '28:1', 'space': '57:1', 'esc': '1:1',
        }
        
        codes = []
        for key in keys.lower().split('+'):
            key = key.strip()
            if key in key_map:
                codes.append(key_map[key])
            else:
                # Single character
                codes.append(f"{ord(key)}:1")
        
        # Add key releases
        release_codes = [code.replace(':1', ':0') for code in codes]
        return codes + release_codes[::-1]
    
    async def mouse_action(self, action='move', x=0, y=0, button=1, **kwargs):
        """Control mouse"""
        if action == 'move':
            cmd = ['ydotool', 'mousemove', '--absolute', str(x), str(y)]
        elif action == 'click':
            cmd = ['ydotool', 'click', str(button)]
        elif action == 'scroll':
            cmd = ['ydotool', 'scroll', str(x), str(y)]
        else:
            return {'error': f'Unknown mouse action: {action}'}
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {'stdout': result.stdout}
    
    async def shell_exec(self, command, **kwargs):
        """Execute shell command"""
        if not self.config.get_bool('security', 'enable_shell_exec'):
            return {'error': 'Shell execution disabled in config'}
        
        result = subprocess.run(command, shell=True, capture_output=True, 
                                text=True, timeout=30)
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    
    async def hyprctl_command(self, command, **kwargs):
        """Execute hyprctl command"""
        cmd = ['hyprctl', command]
        if kwargs.get('json'):
            cmd.append('-j')
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {'stdout': result.stdout, 'stderr': result.stderr}
    
    async def window_control(self, action, target=None, **kwargs):
        """Control windows via hyprctl"""
        commands = {
            'focus': f'dispatch focuswindow {target}',
            'close': f'dispatch closewindow {target}',
            'fullscreen': 'dispatch fullscreen',
            'move': f'dispatch movewindow {kwargs.get("direction", "l")}',
        }
        
        if action not in commands:
            return {'error': f'Unknown window action: {action}'}
        
        return await self.hyprctl_command(commands[action])
    
    async def take_screenshot(self, region=None, **kwargs):
        """Take screenshot"""
        if region:
            cmd = ['grim', '-g', region, '-']
        else:
            cmd = ['grim', '-']
        
        result = subprocess.run(cmd, capture_output=True)
        return {'success': len(result.stdout) > 0, 'size': len(result.stdout)}
    
    async def file_operation(self, operation, path, content=None, **kwargs):
        """File operations"""
        if not self.config.get_bool('security', 'enable_file_ops'):
            return {'error': 'File operations disabled'}
        
        from pathlib import Path
        p = Path(path).expanduser()
        
        if operation == 'read':
            return {'content': p.read_text()}
        elif operation == 'write':
            p.write_text(content)
            return {'success': True}
        elif operation == 'append':
            with p.open('a') as f:
                f.write(content)
            return {'success': True}
        else:
            return {'error': f'Unknown file operation: {operation}'}