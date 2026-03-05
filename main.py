import os
import json
import urllib.request
import urllib.error
import time
import pathlib

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Printify Bulk Uploader (GitHub Raw)",
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
STATE_FILE = "/tmp/uploaded_files.json"

ROOT = pathlib.Path(__file__).resolve().parent

# ── Load designs.json (with full error visibility) ────────────────────────────
def load_design_filenames() -> list[str]:
    file_path = ROOT / "designs.json"
    try:
        if not file_path.exists():
            return ["ERROR: designs.json not found in deployment"]
        with open(file_path) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return ["ERROR: designs.json is not a valid array"]
    except json.JSONDecodeError as e:
        return [f"ERROR: Invalid JSON in designs.json → {e}"]
    except Exception as e:
        return [f"ERROR: Could not read designs.json → {e}"]

DESIGN_FILENAMES = load_design_filenames()

# ── Helpers ───────────────────────────────────────────────────────────────────
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
    public_url = f"{GITHUB_BASE_URL}/{filename}"
    payload = json.dumps({"file_name": filename, "url": public_url}).encode()

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
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode()
    except Exception as e:
        return False, str(e)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": "Printify Bulk Uploader (GitHub Raw) is live",
        "total_designs": len(DESIGN_FILENAMES),
        "github_base": GITHUB_BASE_URL,
    }

@app.get("/debug")
def debug():
    json_path = ROOT / "designs.json"
    return {
        "github_base_url": GITHUB_BASE_URL,
        "total_designs": len(DESIGN_FILENAMES),
        "first_10_designs": DESIGN_FILENAMES[:10] if DESIGN_FILENAMES else [],
        "designs_json_exists": json_path.exists(),
        "designs_json_size_bytes": json_path.stat().st_size if json_path.exists() else 0,
        "token_set": bool(PRINTIFY_TOKEN),
        "state_file_exists": os.path.exists(STATE_FILE),
    }

@app.get("/status")
def status():
    uploaded = load_state()
    pending = [f for f in DESIGN_FILENAMES if f not in uploaded and not f.startswith("ERROR")]

    return {
        "total_files": len(DESIGN_FILENAMES),
        "total_uploaded": len(uploaded),
        "remaining": len(pending),
        "percent_done": round(len(uploaded) / max(len(DESIGN_FILENAMES), 1) * 100, 1),
        "pending_files_sample": pending[:50],
    }

@app.get("/upload")
@app.post("/upload")
def upload():
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN env var is not set"})

    if any(f.startswith("ERROR") for f in DESIGN_FILENAMES):
        return JSONResponse(
            status_code=500,
            content={"error": "designs.json failed to load", "details": DESIGN_FILENAMES}
        )

    uploaded = load_state()
    pending = [f for f in DESIGN_FILENAMES if f not in uploaded]

    if not pending:
        return {"status": "complete", "message": "All designs already uploaded"}

    batch = pending[:BATCH_SIZE]
    succeeded = []
    failed = []

    for filename in batch:
        ok, resp = upload_file(filename)
        if ok:
            succeeded.append(filename)
            uploaded.add(filename)
        else:
            failed.append({"file": filename, "error": str(resp)[:500]})
        time.sleep(SLEEP_BETWEEN)

    save_state(uploaded)

    return {
        "status": "complete" if len(pending) <= BATCH_SIZE else "partial",
        "batch_size": len(batch),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "failed_details": failed,
        "remaining": len(pending) - len(batch),
        "total_uploaded": len(uploaded),
    }
