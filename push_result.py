import os, sys, json, base64, urllib.request

files = [f for f in os.listdir('.') if f.endswith('_result.json')]
if not files:
    files = [f for f in os.listdir('.') if f.startswith(sys.argv[1] if len(sys.argv) > 1 else "nfp") and f.endswith('.json')]
if not files:
    print("No result file")
    sys.exit(0)

with open(files[0]) as f:
    content = f.read()

t = sys.argv[1] if len(sys.argv) > 1 else "nfp"
rid = os.environ.get('GITHUB_RUN_ID', '0')
data = json.dumps({"message": f"{t} result", "content": base64.b64encode(content.encode()).decode()}).encode()
url = f"https://api.github.com/repos/Pixel6068/nfp-telegram-bot/contents/results/{t}_{rid}.json"

req = urllib.request.Request(url, data=data, method="PUT")
req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
req.add_header("Accept", "application/vnd.github+json")
req.add_header("Content-Type", "application/json")

try:
    resp = urllib.request.urlopen(req)
    print(f"OK: {resp.status}")
except Exception as e:
    print(f"Failed: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode()[:200])
