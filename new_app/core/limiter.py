"""
Rate-limiter — Flask-compatible sliding-window implementation.

``slowapi`` is ASGI-only and does not wrap Flask routes.  This module
provides a minimal, dependency-free sliding-window counter that works
inside the Flask WSGI request context.

Usage in Flask routes::

    from new_app.core.limiter import rate_limit

    @auth_bp.route("/login", methods=["GET", "POST"])
    @rate_limit(max_calls=10, window_seconds=60)
    def login():
        ...

Thread-safety: a single ``threading.Lock`` guards the shared state.
State is in-process only — acceptable for single-worker deployments
(cPanel Passenger, gunicorn −w 1).  For multi-worker setups, swap the
in-memory store for a Redis backend.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from functools import wraps
from threading import Lock
from typing import Callable

from flask import jsonify, make_response, request

logger = logging.getLogger(__name__)

# ── Sliding-window store ─────────────────────────────────────────
# { ip_key → deque of monotonic timestamps within the current window }
_counters: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def rate_limit(max_calls: int, window_seconds: int = 60) -> Callable:
    """
    Decorator: enforce a sliding-window rate limit keyed by client IP.

    If the decorated route receives more than ``max_calls`` requests from
    the same IP within ``window_seconds``, subsequent calls return HTTP 429.

    Args:
        max_calls:       Maximum allowed calls in the window.
        window_seconds:  Length of the sliding window in seconds.

    Returns:
        A Flask route decorator.

    Example::

        @auth_bp.route("/login", methods=["GET", "POST"])
        @rate_limit(max_calls=10, window_seconds=60)
        def login():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = request.remote_addr or "unknown"
            now = time.monotonic()
            cutoff = now - window_seconds

            with _lock:
                q = _counters[key]
                # Evict timestamps outside the current window
                while q and q[0] < cutoff:
                    q.popleft()

                if len(q) >= max_calls:
                    logger.warning(
                        "[RateLimit] %s exceeded %d calls / %ds on %s",
                        key, max_calls, window_seconds, request.path,
                    )
                    resp = make_response(
                        "Demasiados intentos. Espere un momento antes de volver a intentarlo.",
                        429,
                    )
                    resp.headers["Retry-After"] = str(window_seconds)
                    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
                    return resp

                q.append(now)

            return f(*args, **kwargs)
        return wrapper
    return decorator

