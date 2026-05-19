import os, sys, json, base64, subprocess

# Find result file
files = [f for f in os.listdir('.') if f.endswith('_result.json')]
if not files:
    files = [f for f in os.listdir('.') if f.startswith(sys.argv[1] if len(sys.argv) > 1 else "nfp") and f.endswith('.json')]
if not files:
    print("No result file")
    sys.exit(0)

t = sys.argv[1] if len(sys.argv) > 1 else "nfp"
rid = os.environ.get('GITHUB_RUN_ID', '0')

# Copy to results dir in the current checkout
import shutil
os.makedirs("results", exist_ok=True)
shutil.copy(files[0], f"results/{t}_{rid}.json")

# Configure git and commit
subprocess.run(["git", "config", "user.email", "bot@local"], capture_output=True)
subprocess.run(["git", "config", "user.name", "Bot"], capture_output=True)
subprocess.run(["git", "add", f"results/{t}_{rid}.json"], capture_output=True)
r = subprocess.run(["git", "commit", "-m", f"{t} result {rid}"], capture_output=True, text=True)
print(r.stdout.strip())
r = subprocess.run(["git", "push"], capture_output=True, text=True)
print(r.stdout.strip()[:200])
print(f"exit: {r.returncode}")
if r.returncode != 0:
    print(r.stderr[:300])
