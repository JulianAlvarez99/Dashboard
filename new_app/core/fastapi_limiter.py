"""
Rate-limiter para FastAPI — middleware ASGI de sliding-window.

Mismo algoritmo que core/limiter.py (Flask) pero implementado como
Starlette middleware para poder usarse con FastAPI.

Límites configurables por path prefix:
  /api/v1/dashboard/data  → 60 requests / minuto por IP
  /api/v1/system/         → 20 requests / minuto (admin endpoints)
  /api/v1/               → 200 requests / minuto por IP (general)
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Dict, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# Per-key sliding-window counters. key = "ip:path"
_counters: Dict[str, deque] = defaultdict(deque)
_lock = Lock()

# (path_prefix, max_calls, window_seconds)
# More specific prefixes must come FIRST — first match wins.
RATE_RULES: List[Tuple[str, int, int]] = [
    ("/api/v1/dashboard/data", 60,  60),   # 60 req/min per IP
    ("/api/v1/system/",        20,  60),   # 20 req/min (admin)
    ("/api/v1/",               200, 60),   # 200 req/min general
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI sliding-window rate-limiter middleware."""

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        rule = _match_rule(path)
        if rule is None:
            return await call_next(request)

        max_calls, window_seconds = rule
        key = f"{client_ip}:{path}"
        now = time.monotonic()
        cutoff = now - window_seconds

        with _lock:
            q = _counters[key]
            # Evict timestamps outside the window
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_calls:
                logger.warning(
                    "[RateLimit:FastAPI] %s → %s (limit %d/%ds)",
                    client_ip, path, max_calls, window_seconds,
                )
                return PlainTextResponse(
                    "Too many requests. Please wait.",
                    status_code=429,
                    headers={"Retry-After": str(window_seconds)},
                )
            q.append(now)

        return await call_next(request)


def _match_rule(path: str) -> Tuple[int, int] | None:
    """Return (max_calls, window_seconds) for the first matching prefix, or None."""
    for prefix, max_calls, window in RATE_RULES:
        if path.startswith(prefix):
            return max_calls, window
    return None
