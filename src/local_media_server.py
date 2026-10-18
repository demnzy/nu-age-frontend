import hashlib
import os
import re
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

_server = None
_server_thread = None
_port = None
_root_dir = None
_lock = threading.Lock()
_registered_tokens: Dict[str, str] = {}


class _CORSRequestHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler that serves registered media files and root directory files with RFC 7233
    HTTP 206 Partial Content (Range requests) for audio/video players, and injects CORS headers.
    """
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def _resolve_target_file(self) -> Optional[str]:
        clean_path = self.path.split('?')[0].split('#')[0]
        if clean_path.startswith('/stream/'):
            token_with_ext = clean_path[len('/stream/'):]
            token = os.path.splitext(token_with_ext)[0]
            with _lock:
                registered = _registered_tokens.get(token)
            if registered and os.path.exists(registered):
                return registered
            return None

        # Fall back to root_dir translation
        try:
            translated = self.translate_path(self.path)
            if os.path.exists(translated) and os.path.isfile(translated):
                return translated
        except Exception:
            pass
        return None

    def do_HEAD(self):
        file_path = self._resolve_target_file()
        if file_path and os.path.isfile(file_path):
            try:
                total_size = os.path.getsize(file_path)
                ctype = self.guess_type(file_path) or 'application/octet-stream'
                self.send_response(200, "OK")
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(total_size))
                self.end_headers()
                return
            except Exception as ex:
                logger.debug(f"HEAD handler notice: {ex}")
        super().do_HEAD()

    def do_GET(self):
        """Custom GET handler with native RFC 7233 Range request support."""
        file_path = self._resolve_target_file()
        if file_path and os.path.isfile(file_path):
            return self._serve_file_with_range(file_path)
        return super().do_GET()

    def _serve_file_with_range(self, path: str):
        try:
            total_size = os.path.getsize(path)
            ctype = self.guess_type(path) or 'application/octet-stream'
            range_header = self.headers.get('Range')

            if range_header:
                match = re.match(r'bytes=(\d+)-(\d*)', range_header.strip())
                if match:
                    start = int(match.group(1))
                    end_group = match.group(2)
                    end = int(end_group) if end_group else total_size - 1

                    if start >= total_size or (end < start):
                        self.send_error(416, "Requested Range Not Satisfiable")
                        return

                    end = min(end, total_size - 1)
                    content_length = (end - start) + 1

                    self.send_response(206, "Partial Content")
                    self.send_header('Content-Type', ctype)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{total_size}')
                    self.send_header('Content-Length', str(content_length))
                    self.end_headers()

                    with open(path, 'rb') as f:
                        f.seek(start)
                        bytes_to_send = content_length
                        chunk_size = 65536
                        while bytes_to_send > 0:
                            read_size = min(chunk_size, bytes_to_send)
                            chunk = f.read(read_size)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_to_send -= len(chunk)
                    return

            # Full file GET request
            self.send_response(200, "OK")
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(total_size))
            self.end_headers()

            with open(path, 'rb') as f:
                chunk_size = 65536
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as ex:
            logger.debug(f"Media server serve notice: {ex}")

    # Mute access logs to avoid spamming the console during video/audio playback
    def log_message(self, format, *args):
        pass


def ensure_started(root_dir: Optional[str] = None):
    """
    Ensures that the local media server is running in a background thread, serving
    files on 127.0.0.1 on an ephemeral port.
    """
    global _server, _server_thread, _port, _root_dir
    with _lock:
        if _server is not None:
            return

        if not root_dir:
            try:
                from src.download_manager import _course_assets_root
                root_dir = _course_assets_root()
            except Exception:
                root_dir = os.path.join(os.getcwd(), "app_data")

        _root_dir = root_dir
        os.makedirs(root_dir, exist_ok=True)

        handler = lambda *args, **kwargs: _CORSRequestHandler(*args, directory=root_dir, **kwargs)

        # ThreadingHTTPServer handles connections concurrently
        _server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        _port = _server.server_address[1]

        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
        logger.info(f"local_media_server started on http://127.0.0.1:{_port} serving {_root_dir}")


def asset_url(local_path: str) -> str:
    """
    Given an absolute local filesystem path, registers the file and returns a
    clean, RFC-compliant http://127.0.0.1:<port>/stream/<token>.<ext> URL
    for playback. Starts the server lazily if not already started.
    Works identically across Windows, Android, Linux, and Web.
    """
    global _server, _port, _registered_tokens

    if _server is None:
        ensure_started()

    if not local_path:
        return ""

    abs_path = os.path.abspath(os.path.normpath(str(local_path)))
    _, ext = os.path.splitext(abs_path)
    if not ext:
        ext = ".mp3"

    # Generate deterministic 16-char token for this exact file path
    token = hashlib.sha1(abs_path.encode('utf-8', errors='ignore')).hexdigest()[:16]
    with _lock:
        _registered_tokens[token] = abs_path

    return f"http://127.0.0.1:{_port}/stream/{token}{ext}"

