"""Container health check: exits 0 when Streamlit's health endpoint answers "ok"."""

import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=5) as resp:
        sys.exit(0 if resp.read().strip() == b"ok" else 1)
except Exception:  # noqa: BLE001
    sys.exit(1)
