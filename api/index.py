from http.server import BaseHTTPRequestHandler
import os
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.getenv("PRINTIFY_TOKEN")  # Add this in Vercel Dashboard → Environment Variables
        domain = os.getenv("VERCEL_URL") or "your-project-name.vercel.app"  # Vercel sets this automatically
        base_url = f"https://{domain}/designs/"

        uploaded = 0
        designs_dir = "public/designs"  # Vercel mounts the whole repo

        for filename in os.listdir(designs_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
                image_url = base_url + filename
                
                payload = {
                    "file_name": filename,
                    "url": image_url
                }
                
                r = requests.post(
                    "https://api.printify.com/v1/uploads/images.json",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                
                if r.status_code == 200:
                    uploaded += 1
                    print(f"✅ Uploaded: {filename}")
                else:
                    print(f"❌ Failed {filename}: {r.text}")

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "complete",
            "uploaded": uploaded,
            "total_found": len([f for f in os.listdir(designs_dir) if f.lower().endswith((".png",".jpg",".jpeg",".svg",".webp"))])
        }).encode())
