import os, json, base64, glob, sys

token = os.environ["PAT_TOKEN"]
t = sys.argv[1] if len(sys.argv) > 1 else "nfp"

files = glob.glob(f"{t}_result.json")
if not files:
    files = glob.glob(f"{t}_*.json")
if not files:
    print(f"No result file found for {t}")
    sys.exit(0)

with open(files[0]) as f:
    content = f.read()

payload = json.dumps({
    "message": f"{t} result",
    "content": base64.b64encode(content.encode()).decode()
}).encode()

import urllib.request
url = f"https://api.github.com/repos/Pixel6068/autoclaw-inbox/contents/data/{t}_{os.environ.get('GITHUB_RUN_ID','0')}.json"
req = urllib.request.Request(url, data=payload, method="PUT")
req.add_header("Authorization", f"Bearer {token}")
req.add_header("Accept", "application/vnd.github+json")
req.add_header("Content-Type", "application/json")

try:
    resp = urllib.request.urlopen(req)
    print(f"OK: {resp.status}")
except Exception as e:
    print(f"Push failed: {e}")
