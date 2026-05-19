import os, sys, json, base64

# Find result file
files = [f for f in os.listdir('.') if f.endswith('_result.json')]
if not files:
    files = [f for f in os.listdir('.') if f.startswith(sys.argv[1] if len(sys.argv) > 1 else "nfp") and f.endswith('.json')]
if not files:
    print("No result file")
    sys.exit(0)

with open(files[0]) as f:
    result = json.load(f)

# Print everything in a line-by-line format for AutoClaw to parse
print("=== AUTOCLAW RESULT ===")
print(json.dumps(result))
print("=== END ===")
