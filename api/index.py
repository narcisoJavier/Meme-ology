from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import traceback

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        debug_info = {
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "file_dir": os.path.dirname(os.path.abspath(__file__)),
            "parent_dir": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sys_path": sys.path[:5],
            "cwd_files": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else [],
        }

        # Try inserting parent dir
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        try:
            from app.main import app
            debug_info["app_imported"] = True
            debug_info["app_routes"] = [r.path for r in app.routes if hasattr(r, "path")]
        except Exception as e:
            debug_info["app_imported"] = False
            debug_info["error"] = str(e)
            debug_info["traceback"] = traceback.format_exc()

        self.wfile.write(json.dumps(debug_info, indent=2).encode('utf-8'))
