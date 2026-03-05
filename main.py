import os
import json
import urllib.request
import urllib.error
import time
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="Printify Uploader - Debug Mode",
    docs_url="/docs",
    redoc_url="/redoc",
)

PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
GITHUB_BASE_URL = os.getenv(
    "GITHUB_BASE_URL",
    "https://raw.githubusercontent.com/victoralaba/email-sender/main/public/designs"
)

BATCH_SIZE = 25
SLEEP_BETWEEN = 0.6

# ── Global error handler (this is what shows the real 500 cause) ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc().splitlines()[-10:]  # last 10 lines
        }
    )

# ── Safe request helper ───────────────────────────────────────────────────────
def make_request(method: str, url: str, data=None):
    headers = {
        "Authorization": f"Bearer {PRINTIFY_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://printify.com/",
        "Origin": "https://printify.com"
    }
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read()
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        return False, {"status": e.code, "body": body[:2000]}
    except Exception as e:
        return False, {"error": str(e)}

# ── Models ────────────────────────────────────────────────────────────────────
class BatchUploadRequest(BaseModel):
    filenames: List[str]

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Ready — go to /docs"}

@app.get("/debug")
def debug():
    return {"token_set": bool(PRINTIFY_TOKEN)}

@app.get("/list-uploads")
def list_uploads():
    if not PRINTIFY_TOKEN:
        raise ValueError("PRINTIFY_TOKEN is not set")
    success, result = make_request("GET", "https://api.printify.com/v1/uploads.json")
    if not success:
        raise Exception(f"List failed: {result}")
    return {"total": len(result), "images": result}

@app.post("/archive-all")
def archive_all(confirm: str = "no"):
    if confirm != "YES_ARCHIVE_ALL":
        return {"message": "Send ?confirm=YES_ARCHIVE_ALL or body {\"confirm\": \"YES_ARCHIVE_ALL\"}"}

    if not PRINTIFY_TOKEN:
        raise ValueError("PRINTIFY_TOKEN is not set")

    # List uploads
    success, uploads = make_request("GET", "https://api.printify.com/v1/uploads.json")
    if not success:
        raise Exception(f"Failed to list uploads: {uploads}")

    if not uploads:
        return {"message": "✅ Already empty!"}

    archived = 0
    failed = []

    for img in uploads[:100]:  # safety limit
        image_id = img.get("id")
        if not image_id:
            continue
        archive_url = f"https://api.printify.com/v1/uploads/{image_id}/archive.json"
        success, result = make_request("POST", archive_url, data=b'{}')
        if success:
            archived += 1
        else:
            failed.append({"id": image_id, "error": result})
        time.sleep(0.5)

    return {
        "status": "done",
        "archived": archived,
        "failed": failed,
        "message": f"Archived {archived} files. Call again if more remain."
    }

@app.post("/upload-batch")
def upload_batch(request: BatchUploadRequest):
    if not PRINTIFY_TOKEN:
        raise ValueError("PRINTIFY_TOKEN is not set")

    pending = list(request.filenames)
    batch = pending[:BATCH_SIZE]
    succeeded = []
    failed = []

    for filename in batch:
        public_url = f"{GITHUB_BASE_URL}/{filename}"
        payload = json.dumps({"file_name": filename, "url": public_url}).encode()
        success, result = make_request("POST", "https://api.printify.com/v1/uploads/images.json", data=payload)
        if success:
            succeeded.append(filename)
        else:
            failed.append({"file": filename, "error": result})
        time.sleep(SLEEP_BETWEEN)

    remaining = [f for f in pending if f not in succeeded]

    return {
        "batch_processed": len(batch),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "failed_details": failed,
        "remaining_count": len(remaining),
        "remaining_files": remaining[:400],
        "note": "Copy remaining_files for next call"
    }
