import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

_server = None
_server_thread = None
_port = None
_root_dir = None
_lock = threading.Lock()

class _CORSRequestHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler that serves files from a specific directory and injects CORS headers
    so that local webviews/players aren't blocked by cross-origin restrictions.
    """
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    # Mute access logs to avoid spamming the console during video playback
    def log_message(self, format, *args):
        pass

def ensure_started(root_dir: str):
    """
    Ensures that the local media server is running in a background thread, serving
    files rooted at `root_dir`. Binds to 127.0.0.1 on an ephemeral port.
    """
    global _server, _server_thread, _port, _root_dir
    with _lock:
        if _server is not None:
            if _root_dir != root_dir:
                logger.warning(f"local_media_server requested to start on {root_dir} but is already running on {_root_dir}")
            return
            
        _root_dir = root_dir
        os.makedirs(root_dir, exist_ok=True)
        
        handler = lambda *args, **kwargs: _CORSRequestHandler(*args, directory=root_dir, **kwargs)
        
        # Port 0 asks the OS to assign an available port
        _server = HTTPServer(('127.0.0.1', 0), handler)
        _port = _server.server_address[1]
        
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
        logger.info(f"local_media_server started on http://127.0.0.1:{_port} serving {_root_dir}")


def asset_url(local_path: str) -> str:
    """
    Given an absolute local filesystem path, returns an http://127.0.0.1:<port>/... URL
    for playback. Starts the server lazily if not already started.
    """
    global _server, _root_dir, _port
    
    if _server is None:
        # Lazy initialization fallback if ensure_started wasn't called manually
        from src.download_manager import _course_assets_root
        ensure_started(_course_assets_root())
        
    try:
        rel_path = os.path.relpath(local_path, _root_dir)
    except ValueError:
        # If the path isn't relative to root_dir (e.g., different drive on Windows),
        # return it unchanged as we can't serve it.
        return local_path
        
    if rel_path.startswith(".."):
        # Path is outside the served directory
        return local_path
        
    # Standardize path separators to URL forward slashes
    rel_path = rel_path.replace(os.sep, '/')
    
    # URL encode the path components (handling spaces, special chars) while keeping slashes
    url_path = quote(rel_path)
    
    return f"http://127.0.0.1:{_port}/{url_path}"
