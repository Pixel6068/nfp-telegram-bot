import os, json, base64, sys, requests

token = os.environ["PAT_TOKEN"]
t = sys.argv[1] if len(sys.argv) > 1 else "nfp"

files = [f for f in os.listdir('.') if f.endswith('_result.json')]
if not files:
    files = [f for f in os.listdir('.') if f.startswith(t) and f.endswith('.json')]
if not files:
    print(f"No result file for {t}")
    sys.exit(0)

with open(files[0]) as f:
    content = f.read()

data = json.dumps({"message": f"{t} result", "content": base64.b64encode(content.encode()).decode()})
url = f"https://api.github.com/repos/Pixel6068/autoclaw-inbox/contents/data/{t}_{os.environ.get('GITHUB_RUN_ID','0')}.json"
print(f"Pushing to: {url}")

r = requests.put(url, json=json.loads(data), headers={
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json"
})
print(f"HTTP {r.status_code}: {r.json().get('content',{}).get('name','ok') if r.ok else r.text[:200]}")
