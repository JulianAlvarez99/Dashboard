"""
Camet Analytics — Application Runner.

Usage:
    python run_new.py          → Both servers (API + Web)
    python run_new.py both     → Both servers (API + Web)
    python run_new.py api      → Only FastAPI  (port 8000)
    python run_new.py web      → Only Flask    (port 5000)
"""

import signal
import subprocess
import sys
import time

import uvicorn

from new_app.core.config import settings


def run_fastapi() -> None:
    """Start the FastAPI data-engine on port 8000."""
    print("🚀 FastAPI → http://localhost:8000")
    print("📄 Docs    → http://localhost:8000/api/docs")
    uvicorn.run(
        "new_app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


def run_flask() -> None:
    """Start the Flask SSR frontend on port 5000."""
    print("🌐 Flask   → http://localhost:5000")
    from new_app.flask_app import create_flask_app

    app = create_flask_app()
    app.run(host="0.0.0.0", port=settings.FLASK_PORT, debug=settings.DEBUG)


def run_both() -> None:
    """Launch FastAPI as a subprocess, Flask in the main process."""
    sep = "=" * 60
    print(sep)
    print("  Camet Analytics v2.0 — Starting both servers")
    print(f"  API:  http://localhost:8000  (FastAPI)")
    print(f"  Web:  http://localhost:{settings.FLASK_PORT}  (Flask)")
    print(f"  Docs: http://localhost:8000/api/docs")
    print(sep)

    api_proc = subprocess.Popen(
        [sys.executable, sys.argv[0], "api"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    time.sleep(2)

    def cleanup(signum=None, frame=None):
        print("\n🛑 Shutting down both servers …")
        api_proc.terminate()
        try:
            api_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        run_flask()
    finally:
        cleanup()


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    runners = {"api": run_fastapi, "web": run_flask, "both": run_both}
    runner = runners.get(mode)
    if runner is None:
        print(f"Unknown mode '{mode}'. Use: api | web | both")
        sys.exit(1)
    runner()
