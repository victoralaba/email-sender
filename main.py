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

# ── HARD-CODED DESIGN LIST (no extra files!) ──────────────────────────────────
DESIGN_FILENAMES = [
    "0001.png", "0001.svg", "0002.png", "0002.svg", "0003.png", "0003.svg",
    "0004.png", "0004.svg", "0005.png", "0005.svg", "0006.png", "0006.svg",
    "0007.png", "0007.svg", "0008.png", "0008.svg", "0009.png", "0009.svg",
    "0010.png", "0010.svg", "0011.png", "0011.svg", "0012.png", "0012.svg",
    "0013.png", "0013.svg", "0014.png", "0014.svg", "0015.png", "0015.svg",
    "0016.png", "0016.svg", "0017.png", "0017.svg", "0018.png", "0018.svg",
    "0019.png", "0019.svg", "0020.png", "0020.svg", "0021.png", "0021.svg",
    "0022.png", "0022.svg", "0023.png", "0023.svg", "0024.png", "0024.svg",
    "0025.png", "0025.svg", "0026.png", "0026.svg", "0027.png", "0027.svg",
    "0028.png", "0028.svg", "0029.png", "0029.svg", "0030.png", "0030.svg",
    "0031.png", "0031.svg", "0032.png", "0032.svg", "0033.png", "0033.svg",
    "0034.png", "0034.svg", "0035.png", "0035.svg", "0036.png", "0036.svg",
    "0037.png", "0037.svg", "0038.png", "0038.svg", "0039.png", "0039.svg",
    "0040.png", "0040.svg", "0041.png", "0041.svg", "0042.png", "0042.svg",
    "0043.png", "0043.svg", "0044.png", "0044.svg", "0045.png", "0045.svg",
    "0046.png", "0046.svg", "0047.png", "0047.svg", "0048.png", "0048.svg",
    "0049.png", "0049.svg", "0050.png", "0050.svg", "0051.png", "0051.svg",
    "0052.png", "0052.svg", "0053.png", "0053.svg", "0054.png", "0054.svg",
    "0055.png", "0055.svg", "0056.png", "0056.svg", "0057.png", "0057.svg",
    "0058.png", "0058.svg", "0059.png", "0059.svg", "0060.png", "0060.svg",
    "0061.png", "0061.svg", "0062.png", "0062.svg", "0063.png", "0063.svg",
    "0064.png", "0064.svg", "0065.png", "0065.svg", "0066.png", "0066.svg",
    "0067.png", "0067.svg", "0068.png", "0068.svg", "0069.png", "0069.svg",
    "0070.png", "0070.svg", "0071.png", "0071.svg", "0072.png", "0072.svg",
    "0073.png", "0073.svg", "0074.png", "0074.svg", "0075.png", "0075.svg",
    "0076.png", "0076.svg", "0077.png", "0077.svg", "0078.png", "0078.svg",
    "0079.png", "0079.svg", "0080.png", "0080.svg", "0081.png", "0081.svg",
    "0082.png", "0082.svg", "0083.png", "0083.svg", "0084.png", "0084.svg",
    "0085.png", "0085.svg", "0086.png", "0086.svg", "0087.png", "0087.svg",
    "0088.png", "0088.svg", "0089.png", "0089.svg", "0090.png", "0090.svg",
    "0091.png", "0091.svg", "0092.png", "0092.svg", "0093.png", "0093.svg",
    "0094.png", "0094.svg", "0095.png", "0095.svg", "0096.png", "0096.svg",
    "0097.png", "0097.svg", "0098.png", "0098.svg", "0099.png", "0099.svg",
    "0100.png", "0100.svg", "0101.png", "0101.svg", "0102.png", "0102.svg",
    "0103.png", "0103.svg", "0104.png", "0104.svg", "0105.png", "0105.svg",
    "0106.png", "0106.svg", "0107.png", "0107.svg", "0108.png", "0108.svg",
    "0109.png", "0109.svg", "0110.png", "0110.svg", "0111.png", "0111.svg",
    "0112.png", "0112.svg", "0113.png", "0113.svg",
    "0114.png", "0115.png", "0116.png", "0117.png", "0118.png", "0119.png",
    "0120.png", "0121.png", "0122.png", "0123.png", "0124.png", "0125.png",
    "0126.png", "0127.png", "0128.png", "0129.png", "0130.png", "0131.png",
    "0132.png", "0133.png", "0134.png", "0135.png", "0136.png", "0137.png",
    "0138.png", "0139.png", "0140.png", "0141.png", "0142.png", "0143.png",
    "0144.png", "0145.png", "0146.png", "0147.png", "0148.png", "0149.png",
    "0150.png", "0151.png", "0152.png", "0153.png", "0154.png", "0155.png",
    "0156.png", "0157.png", "0158.png", "0159.png", "0160.png", "0161.png",
    "0162.png", "0163.png", "0164.png", "0165.png", "0166.png", "0167.png",
    "0168.png"
]

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
    return {
        "github_base_url": GITHUB_BASE_URL,
        "total_designs": len(DESIGN_FILENAMES),
        "first_5": DESIGN_FILENAMES[:5],
        "last_5": DESIGN_FILENAMES[-5:],
        "token_set": bool(PRINTIFY_TOKEN),
    }

@app.get("/status")
def status():
    uploaded = load_state()
    pending = [f for f in DESIGN_FILENAMES if f not in uploaded]
    return {
        "total_files": len(DESIGN_FILENAMES),
        "total_uploaded": len(uploaded),
        "remaining": len(pending),
        "percent_done": round(len(uploaded) / max(len(DESIGN_FILENAMES), 1) * 100, 1),
        "pending_sample": pending[:30],
    }

@app.get("/upload")
@app.post("/upload")
def upload():
    if not PRINTIFY_TOKEN:
        return JSONResponse(status_code=500, content={"error": "PRINTIFY_TOKEN not set"})

    uploaded = load_state()
    pending = [f for f in DESIGN_FILENAMES if f not in uploaded]

    if not pending:
        return {"status": "complete", "message": "All done!"}

    batch = pending[:BATCH_SIZE]
    succeeded, failed = [], []

    for filename in batch:
        ok, resp = upload_file(filename)
        if ok:
            succeeded.append(filename)
            uploaded.add(filename)
        else:
            failed.append({"file": filename, "error": str(resp)[:400]})
        time.sleep(SLEEP_BETWEEN)

    save_state(uploaded)

    return {
        "status": "partial" if len(pending) > BATCH_SIZE else "complete",
        "batch_size": len(batch),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "failed_details": failed,
        "remaining": len(pending) - len(batch),
        "total_uploaded": len(uploaded),
    }
