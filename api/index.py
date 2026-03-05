import os
import json
import urllib.request
import urllib.error
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Printify Bulk Uploader",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── config ────────────────────────────────────────────────────────────────────
PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
VERCEL_URL = (
    os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
    or os.getenv("VERCEL_URL", "")
)
DESIGNS_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "designs")

BATCH_SIZE    = 25
SLEEP_BETWEEN = 0.6
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


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Printify uploader is live. Visit /docs for the Swagger UI."}


@app.get("/status")
def status():
    uploaded  = load_state()
    all_files = get_all_design_files()
    pending   = [f for f in all_files if f not in uploaded]

    return {
        "total_files":    len(all_files),
        "total_uploaded": len(uploaded),
        "remaining":      len(pending),
        "percent_done":   round(len(uploaded) / max(len(all_files), 1) * 100, 1),
        "uploaded_files": sorted(uploaded),
        "pending_files":  pending,
    }


@app.get("/upload")
@app.post("/upload")
def upload():
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN is not set"})

    if not VERCEL_URL:
        return JSONResponse(status_code=500, content={"error": "VERCEL_URL not detected — set VERCEL_PROJECT_PRODUCTION_URL in env vars"})

    base = VERCEL_URL.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"

    all_files = get_all_design_files()
    if not all_files:
        return {"status": "error", "message": f"No design files found in: {os.path.abspath(DESIGNS_DIR)}"}

    uploaded = load_state()
    pending  = [f for f in all_files if f not in uploaded]

    if not pending:
        return {
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
        else:
            failed.append({"file": filename, "error": resp})
        time.sleep(SLEEP_BETWEEN)

    save_state(uploaded)

    remaining = len(pending) - len(batch)
    return {
        "status":         "complete" if remaining == 0 else "partial",
        "batch_size":     len(batch),
        "succeeded":      len(succeeded),
        "failed":         len(failed),
        "failed_details": failed,
        "remaining":      remaining,
        "total_files":    len(all_files),
        "total_uploaded": len(uploaded),
    }
