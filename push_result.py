import os, sys, subprocess, shutil

token = os.environ["PAT_TOKEN"]
t = sys.argv[1] if len(sys.argv) > 1 else "nfp"

# Find result file
files = [f for f in os.listdir('.') if f.endswith('_result.json')]
if not files:
    files = [f for f in os.listdir('.') if f.startswith(t) and f.endswith('.json')]
if not files:
    print(f"No result file for {t}")
    sys.exit(0)

src = files[0]
dst = f"data/{t}_{os.environ.get('GITHUB_RUN_ID','0')}.json"

# Copy file into inbox repo and push
inbox = "/tmp/autoclaw-inbox"
if os.path.exists(inbox):
    shutil.rmtree(inbox)

# Clone
subprocess.run(["git", "clone", f"https://x-access-token:{token}@github.com/Pixel6068/autoclaw-inbox.git", inbox], capture_output=True, check=True)
shutil.copy(src, f"{inbox}/{dst}")
subprocess.run(["git", "-C", inbox, "config", "user.email", "bot@local"], capture_output=True)
subprocess.run(["git", "-C", inbox, "config", "user.name", "Bot"], capture_output=True)
subprocess.run(["git", "-C", inbox, "add", dst], capture_output=True)
result = subprocess.run(["git", "-C", inbox, "commit", "-m", f"{t} result"], capture_output=True, text=True)
print(result.stdout.strip())
result = subprocess.run(["git", "-C", inbox, "push"], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"push failed: {result.stderr[:200]}")
