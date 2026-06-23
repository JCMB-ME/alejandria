"""Simple in-memory rate limiter for login attempts.

Per-IP: 5 attempts per minute, 30 per hour. Returns the number of seconds
the caller must wait before retrying, or None if under the limit.

The state lives in process memory (lost on restart). For v1, this is
acceptable: the 5/min limit is what blocks brute-force; the 30/hour
limit is defence-in-depth. If the process restarts, the worst case is
the attacker gets another 5 attempts before the limit kicks in again.

(Future: persist to DB so the limit survives restarts. Phase E or later.)
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

# In-memory per-IP sliding window of (timestamp) tuples.
_per_minute: dict[str, deque[float]] = defaultdict(deque)
_per_hour: dict[str, deque[float]] = defaultdict(deque)
MINUTE_WINDOW = 60
MINUTE_LIMIT = 5
HOUR_WINDOW = 60 * 60
HOUR_LIMIT = 30


def _client_ip(request) -> str:
    """Best-effort client IP. Reads X-Forwarded-For first, then the
    raw client. The reverse proxy is responsible for stripping client-
    supplied X-Forwarded-For (see docs/CONFIGURATION.md).
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _prune(bucket: deque[float], now: float, window: float) -> None:
    """Drop entries older than the window."""
    while bucket and now - bucket[0] > window:
        bucket.popleft()


def check_login_rate_limit(db, request) -> int | None:
    """Return None if under the limit, or seconds-until-retry if over.

    `db` is accepted for API compatibility with the original plan but is
    unused now that we keep the counters purely in memory.
    """
    ip = _client_ip(request)
    now = time.monotonic()

    minute_bucket = _per_minute[ip]
    _prune(minute_bucket, now, MINUTE_WINDOW)
    if len(minute_bucket) >= MINUTE_LIMIT:
        return MINUTE_WINDOW

    hour_bucket = _per_hour[ip]
    _prune(hour_bucket, now, HOUR_WINDOW)
    if len(hour_bucket) >= HOUR_LIMIT:
        return HOUR_WINDOW

    minute_bucket.append(now)
    hour_bucket.append(now)
    return None


def record_login_attempt(db, request) -> None:
    """No-op kept for API compatibility.

    The attempt is already recorded by `check_login_rate_limit` (it
    appends to the per-IP bucket on success). If we ever move to a
    durable counter, this is where the DB write would go.
    """
