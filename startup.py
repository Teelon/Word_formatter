"""Preflight checks — run before the main app to ensure everything is ready."""

import subprocess
import sys
import time
import os

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

    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet"]
    )

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

def _check_lm_studio() -> str:
    """
    Verify LM Studio is running and has a model loaded.
    Returns the model ID on success; exits on timeout.
    """
    import requests  # safe — _check_packages() ran first

    models_url = f"{LM_STUDIO_BASE}/v1/models"

    for attempt in range(1, MAX_RETRIES + 1):
        # -- Is LM Studio reachable? --
        try:
            resp = requests.get(models_url, timeout=5)
            resp.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            print(
                f"⏳ LM Studio is not running — waiting … "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )
            time.sleep(RETRY_DELAY)
            continue
        except requests.RequestException as e:
            print(f"⚠ Unexpected error reaching LM Studio: {e}")
            time.sleep(RETRY_DELAY)
            continue

        # -- Is a model loaded? --
        data = resp.json().get("data", [])
        if not data:
            print(
                f"⏳ LM Studio is running but no model is loaded — "
                f"please load a model. (attempt {attempt}/{MAX_RETRIES})"
            )
            time.sleep(RETRY_DELAY)
            continue

        model_id = data[0].get("id", "unknown-model")
        print(f"✓ LM Studio is running — model loaded: {model_id}")
        return model_id

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
