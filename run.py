"""
Dashboard SaaS Application Runner

Usage:
    python run.py          → Start both servers (API + Web)
    python run.py both     → Start both servers (API + Web)
    python run.py api      → Start only FastAPI (port 8000)
    python run.py web      → Start only Flask (port 5000)
"""

import subprocess
import sys
import time
import signal

import uvicorn
from app.flask_app import create_flask_app
from app.main import create_app


def run_fastapi():
    """Run FastAPI server for API endpoints."""
    print("Starting FastAPI server on http://localhost:8000")
    print("API docs available at http://localhost:8000/api/docs")
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True
    )


def run_flask():
    """Run Flask server for SSR and authentication."""
    print("Starting Flask server on http://localhost:5000")
    app = create_flask_app()
    app.run(host="0.0.0.0", port=5000, debug=True)


def run_both():
    """
    Run both FastAPI and Flask servers simultaneously.
    FastAPI runs as a subprocess, Flask runs in the main process.
    """
    print("=" * 60)
    print("  Dashboard SaaS - Starting both servers")
    print("  API:  http://localhost:8000  (FastAPI)")
    print("  Web:  http://localhost:5000  (Flask)")
    print("  Docs: http://localhost:8000/api/docs")
    print("=" * 60)

    # Start FastAPI as a subprocess
    api_process = subprocess.Popen(
        [sys.executable, "run.py", "api"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    # Give FastAPI a moment to start
    time.sleep(2)

    def cleanup(signum=None, frame=None):
        print("\n🛑 Shutting down both servers...")
        api_process.terminate()
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
        sys.exit(0)

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        run_flask()
    finally:
        cleanup()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "api":
            run_fastapi()
        elif sys.argv[1] == "web":
            run_flask()
        elif sys.argv[1] == "both":
            run_both()
        else:
            print("Usage: python run.py [api|web|both]")
            print("  api  - Start FastAPI server (port 8000)")
            print("  web  - Start Flask server (port 5000)")
            print("  both - Start both servers (default)")
    else:
        # Default: run both
        run_both()
