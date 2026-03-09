"""
run_dashboard_saas.py — Development entry point.

Starts Flask (port 5000) and FastAPI/Uvicorn (port 8000) in
separate daemon threads. Press Ctrl+C to stop both.

Usage:
    python run_dashboard_saas.py
"""
import sys
import time
import threading

import uvicorn


def run_flask() -> None:
    from dashboard_saas.flask_app import flask_app
    from dashboard_saas.core.config import settings

    flask_app.run(
        host="0.0.0.0",
        port=settings.FLASK_PORT,
        debug=False,        # Disable Flask reloader — conflicts with threading
        use_reloader=False,
    )


def run_fastapi() -> None:
    from dashboard_saas.core.config import settings

    uvicorn.run(
        "dashboard_saas.main:app",
        host="0.0.0.0",
        port=settings.FASTAPI_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, name="flask", daemon=True)
    fastapi_thread = threading.Thread(target=run_fastapi, name="fastapi", daemon=True)

    flask_thread.start()
    fastapi_thread.start()

    from dashboard_saas.core.config import settings

    print(f"\n  Dashboard SaaS")
    print(f"  ------------------------------------------")
    print(f"  Flask   -> http://localhost:{settings.FLASK_PORT}/dashboard/")
    print(f"  FastAPI -> http://localhost:{settings.FASTAPI_PORT}/api/v1/system/health")
    print(f"  API Docs-> http://localhost:{settings.FASTAPI_PORT}/api/docs")
    print(f"  ------------------------------------------")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        while flask_thread.is_alive() or fastapi_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
