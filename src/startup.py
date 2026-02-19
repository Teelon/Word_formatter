"""Preflight checks — run before the main app to ensure everything is ready."""

import subprocess
import sys
import time
import os
import shutil
import re
import json

# ── Required packages (import name → pip name) ──────────────────────────
REQUIRED_PACKAGES = {
    "openai":    "openai",
    "pydantic":  "pydantic",
    "docx":      "python-docx",
    "dateutil":  "python-dateutil",
    "requests":  "requests",
}

LM_STUDIO_BASE = "http://localhost:1234"
MAX_RETRIES    = 12      # ~60 seconds of waiting
RETRY_DELAY    = 5       # seconds between retries
PREFERRED_MODEL = "ibm/granite-4-h-tiny"




# ── 1. Package check ────────────────────────────────────────────────────

def _check_packages() -> None:
    """Try to import every required package; auto-install if any are missing."""
    missing: list[str] = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        print("✓ All required packages are installed.")
        return

    print(f"⚠ Missing packages: {', '.join(missing)}")
    print("  Installing now …")

    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    # check if requirements.txt exists since we moved it/deleted it? 
    # Actually user deleted requirements.txt. 
    # So we should probably install by name list.
    
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"]
        )
    except Exception:
         # Fallback if list install fails
         pass

    # Verify everything imports after install
    still_missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            still_missing.append(pip_name)

    if still_missing:
        sys.exit(f"✗ Could not install: {', '.join(still_missing)}. Fix manually and retry.")

    print("✓ Packages installed successfully.")


# ── 2 & 3. LM Studio + model check ─────────────────────────────────────

def _get_first_llm_model() -> str | None:
    """Finds the preferred model via 'lms ls'."""
    if not shutil.which("lms"):
        return None

    try:
        # Run lms ls --json
        cmd = ["lms", "ls", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', shell=True)
        output = result.stdout
        
        # Check if our preferred model is in the output (simple string check is safer/faster for specific target)
        # We need to be careful about substrings, but model keys are usually distinct enough.
        # Let's try JSON parsing to be precise.
        try:
            start = output.find('[')
            end = output.rfind(']')
            if start != -1 and end != -1:
                json_str = output[start:end+1]
                models = json.loads(json_str)
                
                for m in models:
                    if m.get('modelKey') == PREFERRED_MODEL:
                        return PREFERRED_MODEL
        except Exception:
            pass

        # Fallback: simple string check if JSON parsing fails
        if PREFERRED_MODEL in output:
             return PREFERRED_MODEL

    except Exception as e:
        print(f"⚠ Warning: Could not detect models via 'lms ls': {e}")
    
    return None


def _start_server_if_needed():
    import requests
    try:
        requests.get(f"{LM_STUDIO_BASE}/v1/models", timeout=1)
        return  # Already running
    except (requests.ConnectionError, requests.Timeout):
        pass

    print("⚡ LM Studio server not running. Attempting to start...")
    
    if not shutil.which("lms"):
        print("⚠ 'lms' command not found in PATH. Please start LM Studio manually.")
        return

    try:
        subprocess.Popen(["lms", "server", "start"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
                         shell=True)
        print("⏳ Waiting for server to initialize...")
        time.sleep(3) 
    except Exception as e:
        print(f"⚠ Failed to start server check: {e}")


def _check_lm_studio() -> str:
    """
    Verify LM Studio is running and has a model loaded.
    Auto-starts server and auto-loads model if possible.
    Returns the model ID on success; exits on timeout.
    """
    import requests  # safe — _check_packages() ran first

    models_url = f"{LM_STUDIO_BASE}/v1/models"
    
    # Initial check/start
    _start_server_if_needed()

    for attempt in range(1, MAX_RETRIES + 1):
        # -- Is LM Studio reachable? --
        try:
            resp = requests.get(models_url, timeout=5)
            resp.raise_for_status()
            
            data = resp.json().get("data", [])
            
            if data:
                model_id = data[0].get("id", "unknown-model")
                
                if PREFERRED_MODEL and model_id != PREFERRED_MODEL:
                    print(f"⚠ Found loaded model: '{model_id}'")
                    print(f"➤ Target model: '{PREFERRED_MODEL}'. Attempting to switch...")
                    
                    # Try loading directly (LM Studio often handles unloading)
                    try:
                        proc = subprocess.run(
                            ["lms", "load", PREFERRED_MODEL], 
                            capture_output=True, 
                            text=True, 
                            encoding='utf-8', 
                            errors='replace', 
                            shell=True
                        )
                        if proc.returncode != 0:
                             print(f"⚠ Load command failed: {proc.stderr}")
                             # If load failed, maybe we DO need to unload first?
                             print("➤ Attempting explicit unload...")
                             subprocess.run(["lms", "unload", model_id], check=False, shell=True)
                        
                        time.sleep(2)
                        continue
                    except Exception as e:
                        print(f"⚠ Failed to switch model: {e}")
                
                print(f"✓ LM Studio is running — correct model loaded: {model_id}")
                return model_id
            
            # Connected but no model
            # Try to load if we haven't already (or keep trying)
            print(f"⏳ Waiting for model to load... (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            continue

        except (requests.ConnectionError, requests.Timeout):
            print(
                f"⏳ LM Studio is not reachable... waiting for startup? "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )
            # Retry starting if it takes too long?
            if attempt == 3:
                _start_server_if_needed()
                
            time.sleep(RETRY_DELAY)
            continue
        except requests.RequestException as e:
            print(f"⚠ Unexpected error reaching LM Studio: {e}")
            time.sleep(RETRY_DELAY)
            continue

    sys.exit(
        "✗ Timed out waiting for LM Studio. "
        "Please open LM Studio, load a model, and try again."
    )


# ── Public entry point ──────────────────────────────────────────────────

def preflight() -> str:
    """
    Run all preflight checks in order.
    Returns the model ID of the loaded LM Studio model.
    """
    print("\n══ Preflight checks ══════════════════════════════════════")
    _check_packages()
    model_id = _check_lm_studio()
    print("══════════════════════════════════════════════════════════\n")
    return model_id
