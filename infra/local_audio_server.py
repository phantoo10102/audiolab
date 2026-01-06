import threading
import socket
import http.server
import time
from http.server import HTTPServer
import os
from urllib.parse import quote

# --- FIX: Bỏ "ver3." để import đúng từ root chạy ---
from utils.constants import PROJECT_ROOT

_SERVER_INSTANCE = None
_SERVER_PORT = None
_SERVER_THREAD = None
_SERVING_DIR = None


class AudioHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Phục vụ từ PROJECT_ROOT để truy cập được toàn bộ data/output, data/temp...
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        return super().end_headers()

    def log_message(self, format, *args):
        pass


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def start_audio_server():
    global _SERVER_INSTANCE, _SERVER_PORT, _SERVER_THREAD, _SERVING_DIR

    root_dir = str(PROJECT_ROOT)

    if _SERVER_INSTANCE and _SERVING_DIR == root_dir:
        return f"http://localhost:{_SERVER_PORT}"

    _SERVING_DIR = root_dir
    _SERVER_PORT = find_free_port()

    def handler_factory(*args, **kwargs):
        return AudioHandler(*args, **kwargs)

    _SERVER_INSTANCE = HTTPServer(("localhost", _SERVER_PORT), handler_factory)
    _SERVER_THREAD = threading.Thread(target=_SERVER_INSTANCE.serve_forever)
    _SERVER_THREAD.daemon = True
    _SERVER_THREAD.start()

    print(f"🚀 Audio Server started: http://localhost:{_SERVER_PORT} -> {_SERVING_DIR}")
    return f"http://localhost:{_SERVER_PORT}"


def get_audio_url(file_path: str):
    base_url = start_audio_server()

    abs_path = os.path.abspath(file_path)
    root_path = os.path.abspath(str(PROJECT_ROOT))

    # [FIX] Lấy mtime để làm cache buster
    try:
        mtime = int(os.path.getmtime(abs_path))
    except OSError:
        mtime = int(time.time())

    try:
        # Tính relative path từ project root
        rel_path = os.path.relpath(abs_path, root_path)
        rel_path = rel_path.replace(os.sep, "/")

        parts = rel_path.split("/")
        quoted_parts = [quote(p) for p in parts]
        final_path = "/".join(quoted_parts)

        # [FIX] Thêm ?v={mtime}
        return f"{base_url}/{final_path}?v={mtime}"

    except ValueError:
        # Fallback
        return f"{base_url}/{quote(os.path.basename(file_path))}?v={mtime}"
