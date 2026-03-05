import os
import json
import urllib.request
import urllib.error
import time
from http.server import BaseHTTPRequestHandler

# ── config ────────────────────────────────────────────────────────────────────
PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
# Vercel sets VERCEL_URL automatically (no https://)
# VERCEL_PROJECT_PRODUCTION_URL is the stable production URL
VERCEL_URL = (
    os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
    or os.getenv("VERCEL_URL", "")
)
# Path relative to repo root — Vercel deploys the whole repo
DESIGNS_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "designs")

BATCH_SIZE    = 25     # files per cron run (stays under 60s limit)
SLEEP_BETWEEN = 0.6    # seconds between Printify calls (rate-limit safety)
SUPPORTED     = (".png", ".jpg", ".jpeg", ".svg", ".webp")
STATE_FILE    = "/tmp/uploaded_files.json"
# ──────────────────────────────────────────────────────────────────────────────


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
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_state(uploaded: set):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(uploaded), f)


def upload_file(filename: str, base_url: str):
    url = f"{base_url}/designs/{filename}"
    payload = json.dumps({"file_name": filename, "url": url}).encode()
    req = urllib.request.Request(
        "https://api.printify.com/v1/uploads/images.json",
        data=payload,
        headers={
            "Authorization": f"Bearer {PRINTIFY_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode()
    except Exception as e:
        return False, str(e)


def run_upload():
    if not PRINTIFY_TOKEN:
        return 500, {"error": "PRINTIFY_TOKEN is not set in Vercel environment variables"}

    if not VERCEL_URL:
        return 500, {"error": "VERCEL_URL not detected — set VERCEL_PROJECT_PRODUCTION_URL manually in env vars"}

    base = VERCEL_URL.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"

    all_files = get_all_design_files()
    if not all_files:
        return 200, {
            "status": "error",
            "message": f"No design files found. Looked in: {os.path.abspath(DESIGNS_DIR)}",
        }

    uploaded = load_state()
    pending  = [f for f in all_files if f not in uploaded]

    if not pending:
        return 200, {
            "status":         "complete",
            "message":        "All files already uploaded",
            "total_files":    len(all_files),
            "total_uploaded": len(uploaded),
        }

    batch     = pending[:BATCH_SIZE]
    succeeded = []
    failed    = []

    for filename in batch:
        ok, resp = upload_file(filename, base)
        if ok:
            succeeded.append(filename)
            uploaded.add(filename)
            print(f"[upload] ✅ {filename}")
        else:
            failed.append({"file": filename, "error": resp})
            print(f"[upload] ❌ {filename} — {resp}")
        time.sleep(SLEEP_BETWEEN)

    save_state(uploaded)

    remaining = len(pending) - len(batch)
    return 200, {
        "status":         "complete" if remaining == 0 else "partial",
        "batch_size":     len(batch),
        "succeeded":      len(succeeded),
        "failed":         len(failed),
        "failed_details": failed,
        "remaining":      remaining,
        "total_files":    len(all_files),
        "total_uploaded": len(uploaded),
    }


# ── Vercel serverless handler ──────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence noisy default logging

    def do_GET(self):
        """Manual trigger: GET /api/upload"""
        self._respond(*run_upload())

    def do_POST(self):
        """Vercel Cron Jobs use POST"""
        self._respond(*run_upload())

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
