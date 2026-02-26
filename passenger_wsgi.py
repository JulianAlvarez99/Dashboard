"""
passenger_wsgi.py — cPanel / Phusion Passenger entry point
===========================================================

Phusion Passenger (WSGI mode) will import this module and call the
``application`` callable for every HTTP request routed to the Flask
frontend.

Architecture:
  • Flask (SSR + auth)  → served by Passenger on the cPanel domain.
  • FastAPI (data API)  → started as a background subprocess via uvicorn
                          on localhost:8000 (not exposed externally).

cPanel setup:
  1. Upload the project under ~/public_html (or a subdomain root).
  2. Set the Python app path to this file in cPanel Python App manager.
  3. Create .env in the project root (copy .env.example, fill in secrets).
  4. Make sure the virtualenv is activated (cPanel does this automatically).

Environment variable required at minimum:
  FLASK_SECRET_KEY, SECRET_KEY, API_INTERNAL_KEY
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_GLOBAL_NAME
  API_BASE_URL  (e.g. http://127.0.0.1:8000)

Note: Passenger keeps the Python process alive — the uvicorn subprocess
is started once and reused for subsequent requests.  A ``atexit`` handler
cleanly terminates it on reload/shutdown.
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys
import time

# ── Working directory ── Passenger sets cwd to the project root ──
# Ensure the project root is on sys.path so `new_app` is importable.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("passenger_wsgi")

# ── FastAPI subprocess ────────────────────────────────────────────

_fastapi_proc: subprocess.Popen | None = None


def _start_fastapi() -> None:
    """
    Start the FastAPI (uvicorn) server as a background subprocess.

    Binds to 127.0.0.1 — only reachable from the local machine.
    Port is read from FASTAPI_PORT env var (default 8000).
    Uvicorn executable is resolved from the active virtualenv.
    """
    global _fastapi_proc

    api_port = os.environ.get("FASTAPI_PORT", "8000")

    # Determine uvicorn binary path
    venv_bin = os.path.join(sys.prefix, "bin", "uvicorn")
    if sys.platform == "win32":
        venv_bin = os.path.join(sys.prefix, "Scripts", "uvicorn.exe")

    uvicorn_cmd = venv_bin if os.path.isfile(venv_bin) else "uvicorn"

    cmd = [
        uvicorn_cmd,
        "new_app.main:create_fastapi_app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", api_port,
        "--workers", "1",          # single worker — MetadataCache is process-local
        "--log-level", "info",
    ]

    logger.info("Starting FastAPI backend: %s", " ".join(cmd))
    _fastapi_proc = subprocess.Popen(
        cmd,
        cwd=_PROJECT_ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Give uvicorn a moment to bind the port before Flask starts
    time.sleep(1.5)
    if _fastapi_proc.poll() is not None:
        raise RuntimeError(
            f"FastAPI (uvicorn) failed to start — exit code {_fastapi_proc.returncode}"
        )

    logger.info("FastAPI backend running on http://127.0.0.1:%s (PID %d)", api_port, _fastapi_proc.pid)


def _stop_fastapi() -> None:
    """Terminate the uvicorn subprocess on Passenger shutdown / reload."""
    global _fastapi_proc
    if _fastapi_proc and _fastapi_proc.poll() is None:
        logger.info("Stopping FastAPI backend (PID %d)…", _fastapi_proc.pid)
        _fastapi_proc.terminate()
        try:
            _fastapi_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _fastapi_proc.kill()
        _fastapi_proc = None


atexit.register(_stop_fastapi)


# ── Start FastAPI once at import time ────────────────────────────
try:
    _start_fastapi()
except Exception as exc:
    logger.error("Could not start FastAPI backend: %s", exc)
    # Allow Flask to start anyway so login page is reachable
    # and the error is visible in cPanel error logs.


# ── Flask WSGI application ────────────────────────────────────────
from new_app.flask_app import create_flask_app  # noqa: E402

from werkzeug.middleware.dispatcher import DispatcherMiddleware

def _not_found_app(environ, start_response):
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not found"]

_flask_app = create_flask_app()
tenant_slug = os.environ.get("TENANT_SLUG", "").strip("/")

if tenant_slug:
    # Monta Flask bajo /clienteabc — Passenger ve el path completo
    application = DispatcherMiddleware(
        _not_found_app,           # responde 404 para "/"
        {f"/{tenant_slug}": _flask_app}
    )
else:
    application = _flask_app     # fallback raíz

