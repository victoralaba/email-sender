import os
import json
from http.server import BaseHTTPRequestHandler

STATE_FILE  = "/tmp/uploaded_files.json"
DESIGNS_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "designs")
SUPPORTED   = (".png", ".jpg", ".jpeg", ".svg", ".webp")


def get_all_design_files():
    try:
        return sorted([
            f for f in os.listdir(DESIGNS_DIR)
            if f.lower().endswith(SUPPORTED)
        ])
    except FileNotFoundError:
        return []


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return sorted(json.load(f))
        except Exception:
            pass
    return []


class handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        uploaded  = load_state()
        all_files = get_all_design_files()
        pending   = [f for f in all_files if f not in set(uploaded)]

        body = json.dumps({
            "total_files":    len(all_files),
            "total_uploaded": len(uploaded),
            "remaining":      len(pending),
            "percent_done":   round(len(uploaded) / max(len(all_files), 1) * 100, 1),
            "uploaded_files": uploaded,
            "pending_files":  pending,
        }, indent=2).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
