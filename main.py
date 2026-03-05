import os
import json
import urllib.request
import urllib.error
import time
import pathlib
import mimetypes
import base64

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Printify Bulk Uploader",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── config ────────────────────────────────────────────────────────────────────
PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
BASE_URL       = os.getenv("BASE_URL", "").rstrip("/")   # e.g. https://your-app.vercel.app

ROOT        = pathlib.Path(__file__).resolve().parent
DESIGNS_DIR = ROOT / "public" / "designs"

BATCH_SIZE    = 25
SLEEP_BETWEEN = 0.6
SUPPORTED     = (".png", ".jpg", ".jpeg", ".svg", ".webp")
STATE_FILE    = "/tmp/uploaded_files.json"
# ──────────────────────────────────────────────────────────────────────────────




# ── helpers ───────────────────────────────────────────────────────────────────

def get_all_design_files() -> list[str]:
    try:
        return sorted(
            f for f in os.listdir(DESIGNS_DIR)
            if f.lower().endswith(SUPPORTED)
        )
    except FileNotFoundError:
        return []


def load_state() -> set[str]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_state(uploaded: set[str]) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(uploaded), f)


def upload_file(filename: str) -> tuple[bool, object]:
    """Upload a single design file to Printify by sending base64 content."""
    file_path = DESIGNS_DIR / filename
    
    if not file_path.is_file():
        return False, f"File not found on disk: {filename}"
    
    try:
        with open(file_path, "rb") as f:
            content = f.read()
            b64_content = base64.b64encode(content).decode("utf-8")
        
        payload = json.dumps({
            "file_name": filename,
            "contents": b64_content     # ← Printify accepts this field
        }).encode()

        req = urllib.request.Request(
            "https://api.printify.com/v1/uploads/images.json",
            data=payload,
            headers={
                "Authorization": f"Bearer {PRINTIFY_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, json.loads(resp.read())

    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode()
        except:
            err_body = str(e)
        return False, err_body
    except Exception as e:
        return False, str(e)


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "Printify bulk uploader is live.",
        "endpoints": {
            "docs":    "/docs",
            "status":  "/status",
            "upload":  "/upload  (GET or POST)",
            "debug":   "/debug",
            "designs": "/designs/{filename}",
        },
    }


@app.get("/designs/{filename}")
def serve_design(filename: str):
    """Serve a design file directly from the bundled public/designs folder."""
    safe_name = pathlib.Path(filename).name  # prevent path traversal
    file_path = DESIGNS_DIR / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Design '{safe_name}' not found")

    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "application/octet-stream"

    return Response(
        content=file_path.read_bytes(),
        media_type=mime,
        headers={"Cache-Control": "public, max-age=31536000"},
    )


@app.get("/debug")
def debug():
    """Inspect the runtime environment — remove or protect this in production."""
    try:
        files = sorted(os.listdir(DESIGNS_DIR))
    except Exception as e:
        files = [f"ERROR: {e}"]

    return {
        "__file__":         str(pathlib.Path(__file__).resolve()),
        "designs_dir":      str(DESIGNS_DIR),
        "designs_exist":    DESIGNS_DIR.exists(),
        "cwd":              os.getcwd(),
        "base_url":         BASE_URL,
        "token_set":        bool(PRINTIFY_TOKEN),
        "design_files":     files[:20],   # first 20 for safety
        "total_on_disk":    len(files),
    }


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
        return JSONResponse(
            status_code=500,
            content={"error": "PRINTIFY_TOKEN env var is not set"},
        )

    if not BASE_URL:
        return JSONResponse(
            status_code=500,
            content={"error": "BASE_URL env var is not set (e.g. https://your-app.vercel.app)"},
        )

    all_files = get_all_design_files()
    if not all_files:
        return JSONResponse(
            status_code=404,
            content={
                "error":       "No design files found",
                "designs_dir": str(DESIGNS_DIR),
                "tip":         "Check /debug for runtime path info",
            },
        )

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
        ok, resp = upload_file(filename)
        if ok:
            succeeded.append(filename)
            uploaded.add(filename)
        else:
            failed.append({"file": filename, "error": resp})
        time.sleep(SLEEP_BETWEEN)

    save_state(uploaded)

    remaining_after = len(pending) - len(batch)
    return {
        "status":         "complete" if remaining_after == 0 else "partial",
        "batch_size":     len(batch),
        "succeeded":      len(succeeded),
        "failed":         len(failed),
        "failed_details": failed,
        "remaining":      remaining_after,
        "total_files":    len(all_files),
        "total_uploaded": len(uploaded),
    }
