"""Security headers middleware.

Sets a baseline of headers on every response. The CSP is intentionally
permissive enough to keep SvelteKit's inline-style and the reader's
iframe-based EPUB.js renderer working. Each header's purpose is
documented inline; tightening any of them is a breaking change for
some subset of routes and must be done with verification across the
reader and the auth flows.
"""
from __future__ import annotations

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from alejandria.auth.csrf import csrf_protect

# CSP for a SvelteKit SPA + EPUB.js reader.
#   - default-src 'self'                 — same-origin by default
#   - img-src 'self' data: blob:         — covers inline covers and EPUB blob URLs
#   - style-src 'self' 'unsafe-inline'   — SvelteKit emits inline styles
#   - script-src 'self' 'unsafe-inline'  — SvelteKit adapter-static emits a
#                                          small inline boot script that
#                                          imports the entry bundle; without
#                                          'unsafe-inline' the SPA never
#                                          hydrates. The bundle itself is
#                                          same-origin (still gated by 'self').
#   - connect-src 'self' ws: wss:        — Vite HMR in dev; production same-origin
#   - frame-src 'self' blob:             — EPUB.js renders book content in blob: iframes
#   - object-src 'none'                  — no plugins
#   - base-uri 'self'                    — prevents <base> hijacks
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self' ws: wss:; "
    "frame-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # Transport security — 1 year, include subdomains. Only meaningful
        # over HTTPS; the browser ignores it on http://.
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", _CSP)
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests without a valid CSRF token.

    Backed by the csrf_protect() dependency in auth/csrf.py. The
    dependency is the source of truth; the middleware just turns its
    HTTPException into a JSON response so the SPA can show a
    consistent error shape.
    """

    async def dispatch(self, request, call_next):
        try:
            csrf_protect(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        return await call_next(request)
