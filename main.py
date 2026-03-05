import os
import json
import urllib.request
import urllib.error
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Printify Manual Batch Uploader + Archive Tool",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Config ────────────────────────────────────────────────────────────────────
PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
GITHUB_BASE_URL = os.getenv(
    "GITHUB_BASE_URL",
    "https://raw.githubusercontent.com/victoralaba/email-sender/main/public/designs"
)

BATCH_SIZE = 25
SLEEP_BETWEEN = 0.6

# ── Headers to bypass Cloudflare 1010 ─────────────────────────────────────────
HEADERS = {
    "Authorization": f"Bearer {PRINTIFY_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://printify.com/",
    "Origin": "https://printify.com"
}

# ── Upload helper ─────────────────────────────────────────────────────────────
def upload_file(filename: str) -> tuple[bool, object]:
    public_url = f"{GITHUB_BASE_URL}/{filename}"
    payload = json.dumps({"file_name": filename, "url": public_url}).encode()

    req = urllib.request.Request(
        "https://api.printify.com/v1/uploads/images.json",
        data=payload,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return True, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode()[:600]
    except Exception as e:
        return False, str(e)

# ── Request models ────────────────────────────────────────────────────────────
class BatchUploadRequest(BaseModel):
    filenames: List[str]

class ArchiveConfirm(BaseModel):
    confirm: str = "no"   # must be "YES_ARCHIVE_ALL" to actually run

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Printify uploader ready — use /docs"}

@app.get("/debug")
def debug():
    return {"token_set": bool(PRINTIFY_TOKEN), "github_base": GITHUB_BASE_URL}

# ── NEW: List all currently uploaded images on Printify ───────────────────────
@app.get("/list-uploads")
def list_uploads():
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN missing"})

    req = urllib.request.Request(
        "https://api.printify.com/v1/uploads/images.json",
        headers=HEADERS,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return {
                "total": len(data),
                "images": [{"id": img["id"], "file_name": img.get("file_name"), "created_at": img.get("created_at")} 
                           for img in data]
            }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# ── NEW: Archive ALL uploaded images (safe, requires confirmation) ─────────────
@app.post("/archive-all")
def archive_all(confirm: ArchiveConfirm):
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN missing"})

    if confirm.confirm != "YES_ARCHIVE_ALL":
        return {"message": "❌ SAFETY CHECK: Send {\"confirm\": \"YES_ARCHIVE_ALL\"} to actually archive everything."}

    # Get list first
    try:
        req = urllib.request.Request(
            "https://api.printify.com/v1/uploads/images.json",
            headers=HEADERS,
            method="GET",
        )
        with urllib.request.urlopen(req) as resp:
            uploads = json.loads(resp.read())
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to list uploads: {e}"})

    archived = 0
    failed = []

    for img in uploads:
        image_id = img["id"]
        try:
            req = urllib.request.Request(
                f"https://api.printify.com/v1/uploads/{image_id}/archive.json",
                data=b'{}',
                headers=HEADERS,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15):
                archived += 1
            time.sleep(0.3)  # be nice to API
        except Exception as e:
            failed.append({"id": image_id, "error": str(e)[:200]})

    return {
        "status": "done",
        "archived": archived,
        "failed": failed,
        "message": "✅ All previous uploads have been archived. You can now re-upload everything fresh."
    }

# ── Existing manual batch upload (unchanged) ──────────────────────────────────
@app.post("/upload-batch")
def upload_batch(request: BatchUploadRequest):
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN not set"})

    if not request.filenames:
        return {"error": "Provide 'filenames' array"}

    pending = list(request.filenames)
    batch = pending[:BATCH_SIZE]
    succeeded = []
    failed = []

    for filename in batch:
        ok, resp = upload_file(filename)
        if ok:
            succeeded.append(filename)
        else:
            failed.append({"file": filename, "error": resp})
        time.sleep(SLEEP_BETWEEN)

    remaining = [f for f in pending if f not in succeeded]

    return {
        "batch_processed": len(batch),
        "succeeded": succeeded,
        "failed": failed,
        "remaining_count": len(remaining),
        "remaining_files": remaining[:300],
        "note": "Copy the remaining_files array for the next call"
    }
