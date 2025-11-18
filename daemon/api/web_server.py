"""Flask web server for dashboard"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging
import asyncio
from functools import wraps


logger = logging.getLogger('WebServer')


def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


class WebServer:
    def __init__(self, config, daemon):
        self.config = config
        self.daemon = daemon
        self.app = Flask(__name__, 
                         template_folder='../web/templates',
                         static_folder='../web/static')
        CORS(self.app)
        
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/api/query', methods=['POST'])
        @async_route
        async def api_query():
            data = request.json
            query = data.get('query')
            screenshot = data.get('screenshot', False)
            
            if not query:
                return jsonify({'error': 'No query provided'}), 400
            
            result = await self.daemon.process_user_query(query, screenshot)
            return jsonify(result)
        
        @self.app.route('/api/status', methods=['GET'])
        @async_route
        async def api_status():
            state = await self.daemon.context._update_system_state()
            return jsonify({
                'status': 'running',
                'system_state': state
            })
    
    async def start(self):
        """Start web server"""
        from threading import Thread
        
        def run():
            self.app.run(
                host='127.0.0.1',
                port=self.config.port,
                debug=False,
                use_reloader=False
            )
        
        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info(f"Web server started on port {self.config.port}")
    
    async def stop(self):
        logger.info("Web server stopped")