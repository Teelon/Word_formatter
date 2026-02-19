
import subprocess
import json
import sys

try:
    # Run lms ls --json
    result = subprocess.run(["lms", "ls", "--json"], capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"Error running lms ls: {result.stderr}")
        sys.exit(1)
        
    try:
        models = json.loads(result.stdout)
        print(json.dumps(models, indent=2))
    except json.JSONDecodeError:
        print("Could not decode JSON output from lms ls")
        print(result.stdout)

except Exception as e:
    print(f"Exception: {e}")
