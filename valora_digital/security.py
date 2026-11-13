"""Security helpers: CSRF tokens, rate limiting, response headers.

Deliberately dependency-free so the site runs on a plain Flask install.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import Flask, Request, request, session

CSRF_SESSION_KEY = "_csrf_token"


# --------------------------------------------------------------------------
# CSRF
# --------------------------------------------------------------------------
def get_csrf_token() -> str:
    """Return the per-session CSRF token, creating it on first use."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_is_valid() -> bool:
    """True when the request carries the CSRF token stored in the visitor's session."""
    expected = session.get(CSRF_SESSION_KEY, "")
    supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


# --------------------------------------------------------------------------
# Rate limiting (in-process sliding window)
# --------------------------------------------------------------------------
class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per ``window`` seconds for each key.

    State lives in this process's memory, which is right for a single worker
    or small deployment.  With several Gunicorn workers each one keeps its own
    counter, so the effective limit is ``limit * workers``; use a shared store
    (e.g. Flask-Limiter + Redis) if you need a strict global limit.
    """

    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            # Opportunistic cleanup so the dict cannot grow without bound.
            if len(self._hits) > 5000:
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    del self._hits[stale]
            return True

    def retry_after(self, key: str) -> int:
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            return max(1, int(self.window - (time.monotonic() - hits[0])) + 1)


# --------------------------------------------------------------------------
# Privacy helpers
# --------------------------------------------------------------------------
def hash_ip(req: Request, secret: str) -> str:
    """Keyed hash of the client IP, so we can spot repeat abuse without storing raw IPs."""
    ip = req.remote_addr or "unknown"
    return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


# --------------------------------------------------------------------------
# Response headers
# --------------------------------------------------------------------------
# The page loads GSAP/ScrollTrigger (cdnjs), Lenis (jsDelivr) and Google Fonts.
# style-src keeps 'unsafe-inline' because GSAP/ScrollTrigger inject inline
# styles at runtime; scripts remain locked to the hosts below (no inline JS).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def init_app(app: Flask) -> None:
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )
        if request.is_secure and not app.debug:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        # Pages embed a per-visitor CSRF token, so shared caches must not keep them.
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "private, no-cache"
        return response
