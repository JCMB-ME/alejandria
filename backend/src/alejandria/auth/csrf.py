"""CSRF protection via the double-submit cookie pattern.

The SPA stores the token in the `alejandria_csrf` cookie (NOT HttpOnly so
JS can read it) and echoes it in the `X-CSRF-Token` header on every
non-GET request (`frontend/src/lib/api/client.ts:37-42`). This dependency
compares the two and rejects mismatches with 403.

Safe methods (GET, HEAD, OPTIONS) and the unauthenticated endpoints
(`/api/auth/login`, `/api/auth/oidc/*`) bypass the check; the latter
because no session exists yet.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from alejandria.auth.security import constant_time_compare

# Endpoints that intentionally skip CSRF (no session exists yet, or the
# request is intrinsically cross-origin like a preflight).
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EXEMPT_PATHS = (
    "/api/auth/login",
    "/api/auth/login/json",
    "/api/auth/oidc/login",
    "/api/auth/setup-status",
    "/api/auth/register",
    "/api/security/status",
    "/api/health",
    "/api/health/ready",
)


def _path(request: Request) -> str:
    """Strip query string and normalise trailing slash."""
    p = request.url.path.rstrip("/")
    return p or "/"


def csrf_protect(request: Request) -> None:
    """Dependency: enforce CSRF on state-changing requests.

    Mounted as a middleware (CSRFMiddleware) in main.py so every
    endpoint is gated. The dependency shape is kept for future
    per-router overrides.
    """
    if request.method in _SAFE_METHODS:
        return
    if _path(request) in _EXEMPT_PATHS:
        return

    cookie_token = request.cookies.get("alejandria_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )
    if not constant_time_compare(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )
