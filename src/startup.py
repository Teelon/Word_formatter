"""Preflight checks — ensures LM Studio is running, server is active, and the correct model is loaded."""

import subprocess
import sys
import time
import os
import shutil
import json

# ── Configuration ────────────────────────────────────────────────────────
LM_STUDIO_BASE = "http://localhost:1234"
PREFERRED_MODEL = "qwen2.5-3b-instruct"
MAX_RETRIES = 20        # ~100 seconds of waiting
RETRY_DELAY = 5         # seconds between retries

REQUIRED_PACKAGES = {
    "openai":    "openai",
    "pydantic":  "pydantic",
    "docx":      "python-docx",
    "requests":  "requests",
}


# ── 1. Package Check ────────────────────────────────────────────────────

def _check_packages() -> None:
    """Ensure all required Python packages are installed."""
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        print("  ✓ All Python packages installed")
        return

    print(f"  ⚠ Missing: {', '.join(missing)} — installing...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"]
        )
        print("  ✓ Packages installed")
    except Exception:
        sys.exit(f"  ✗ Could not install: {', '.join(missing)}. Fix manually.")


# ── 2. LM Studio Application Check ─────────────────────────────────────

def _is_lm_studio_running() -> bool:
    """Check if LM Studio app is running as a process."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq LM Studio.exe"],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        return "LM Studio.exe" in result.stdout
    except Exception:
        return False


def _start_lm_studio_app():
    """Launch the LM Studio application."""
    # Common install paths on Windows
    possible_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\LM Studio\LM Studio.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe"),
        r"C:\Program Files\LM Studio\LM Studio.exe",
        r"C:\Program Files (x86)\LM Studio\LM Studio.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"  ⚡ Starting LM Studio from: {os.path.basename(path)}")
            subprocess.Popen(
                [path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            print("  ⏳ Waiting for LM Studio to initialize...")
            time.sleep(8)
            return True

    print("  ⚠ Could not find LM Studio install. Please start it manually.")
    return False


# ── 3. Server Check ────────────────────────────────────────────────────

def _is_server_running() -> bool:
    """Check if LM Studio API server is responding."""
    import requests
    try:
        resp = requests.get(f"{LM_STUDIO_BASE}/v1/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _start_server():
    """Start the LM Studio API server via lms CLI."""
    if not shutil.which("lms"):
        print("  ⚠ 'lms' CLI not found. Please start the server manually in LM Studio.")
        return False

    print("  ⚡ Starting API server...")
    try:
        subprocess.run(
            ["lms", "server", "start"],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            shell=True, timeout=15
        )
        time.sleep(3)
        return True
    except Exception as e:
        print(f"  ⚠ Failed to start server: {e}")
        return False


# ── 4. Model Check ─────────────────────────────────────────────────────

def _get_loaded_models() -> list[str]:
    """Get list of currently loaded model IDs from the API."""
    import requests
    try:
        resp = requests.get(f"{LM_STUDIO_BASE}/v1/models", timeout=5)
        data = resp.json().get("data", [])
        return [m.get("id", "") for m in data if m.get("id")]
    except Exception:
        return []


def _is_model_downloaded() -> bool:
    """Check if the preferred model is downloaded locally via lms ls."""
    if not shutil.which("lms"):
        return False
    try:
        result = subprocess.run(
            ["lms", "ls"], capture_output=True, text=True,
            encoding='utf-8', errors='replace', shell=True, timeout=10
        )
        return PREFERRED_MODEL in result.stdout
    except Exception:
        return False


def _download_model() -> bool:
    """Download the preferred model via lms CLI."""
    if not shutil.which("lms"):
        print(f"  ⚠ 'lms' CLI not found. Please download '{PREFERRED_MODEL}' manually in LM Studio.")
        return False

    print(f"  📥 Downloading model: {PREFERRED_MODEL}")
    print(f"     This may take a while depending on your connection...")
    try:
        result = subprocess.run(
            ["lms", "get", PREFERRED_MODEL, "-y"],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            shell=True, timeout=600  # 10 minute timeout for download
        )
        if result.returncode == 0:
            print(f"  ✓ Model downloaded successfully")
            return True
        else:
            print(f"  ⚠ Download may have failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ⚠ Download timed out. Please download manually in LM Studio.")
        return False
    except Exception as e:
        print(f"  ⚠ Download error: {e}")
        return False


def _load_model() -> bool:
    """Load the preferred model via lms CLI."""
    if not shutil.which("lms"):
        print(f"  ⚠ 'lms' CLI not found. Please load '{PREFERRED_MODEL}' manually in LM Studio.")
        return False

    print(f"  📦 Loading model: {PREFERRED_MODEL}")
    try:
        result = subprocess.run(
            ["lms", "load", PREFERRED_MODEL, "-y"],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            shell=True, timeout=120
        )
        if result.returncode == 0:
            print(f"  ✓ Model loaded")
            return True
        else:
            print(f"  ⚠ Load failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ⚠ Load error: {e}")
        return False


# ── Main Preflight Orchestrator ─────────────────────────────────────────

def preflight() -> str:
    """
    Run all preflight checks in order:
    1. Check Python packages
    2. Ensure LM Studio app is running
    3. Ensure API server is started
    4. Ensure model is downloaded and loaded

    Returns the model ID that is ready for use.
    """
    print("\n══ Preflight Checks ══════════════════════════════════════")

    # Step 1: Python packages
    print("\n[1/4] Python Packages")
    _check_packages()

    # Step 2: LM Studio application
    print("\n[2/4] LM Studio Application")
    if _is_lm_studio_running():
        print("  ✓ LM Studio is running")
    else:
        print("  ✗ LM Studio is not running")
        if not _start_lm_studio_app():
            sys.exit("  ✗ Cannot proceed without LM Studio. Please start it manually.")

        # Wait a bit more and re-check
        for i in range(5):
            if _is_lm_studio_running():
                print("  ✓ LM Studio started successfully")
                break
            time.sleep(3)
        else:
            sys.exit("  ✗ LM Studio failed to start. Please start it manually.")

    # Step 3: API server
    print("\n[3/4] API Server")
    if _is_server_running():
        print("  ✓ API server is running")
    else:
        print("  ✗ API server is not running")
        _start_server()

        # Wait for server to come online
        for i in range(MAX_RETRIES):
            if _is_server_running():
                print("  ✓ API server is now running")
                break
            time.sleep(RETRY_DELAY)
        else:
            sys.exit("  ✗ API server failed to start. Please start it manually in LM Studio.")

    # Step 4: Model
    print(f"\n[4/4] Model: {PREFERRED_MODEL}")
    loaded = _get_loaded_models()

    if PREFERRED_MODEL in loaded:
        print(f"  ✓ Model is loaded and ready")
    else:
        if loaded:
            print(f"  ⚠ Wrong model loaded: {loaded[0]}")
            print(f"  ➤ Switching to {PREFERRED_MODEL}...")

        # Check if downloaded
        if not _is_model_downloaded():
            print(f"  ✗ Model not found locally")
            if not _download_model():
                sys.exit(f"  ✗ Cannot proceed without the model. Download '{PREFERRED_MODEL}' in LM Studio.")

        # Load the model
        if not _load_model():
            sys.exit(f"  ✗ Failed to load model. Please load '{PREFERRED_MODEL}' manually in LM Studio.")

        # Wait for model to appear in loaded list
        print("  ⏳ Waiting for model to be ready...")
        for i in range(MAX_RETRIES):
            loaded = _get_loaded_models()
            if any(PREFERRED_MODEL in m for m in loaded):
                print(f"  ✓ Model is loaded and ready")
                break
            time.sleep(RETRY_DELAY)
        else:
            sys.exit("  ✗ Model failed to load. Please load it manually in LM Studio.")

    # Final confirmation
    final_models = _get_loaded_models()
    model_id = next((m for m in final_models if PREFERRED_MODEL in m), final_models[0] if final_models else PREFERRED_MODEL)

    print("\n══════════════════════════════════════════════════════════")
    print(f"  ✓ All checks passed — Model: {model_id}")
    print("══════════════════════════════════════════════════════════\n")

    return model_id
