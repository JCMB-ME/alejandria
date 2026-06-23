"""Public security status endpoint — drives the SPA's default-credentials banner."""
from __future__ import annotations

from fastapi import APIRouter

from alejandria.config import get_settings

router = APIRouter()

_KNOWN_BAD_SECRETS = frozenset({
    "change-me-in-production-please",
    "change-me-to-a-long-random-string",
    "changeme",
    "",
})
_KNOWN_BAD_PASSWORDS = frozenset({"changeme", ""})


@router.get("/status")
async def security_status() -> dict:
    """Returns whether the instance is using well-known default values.

    No secrets are exposed — only a list of which defaults are in use.
    The SPA renders a yellow banner when any are.
    """
    settings = get_settings()
    reasons: list[str] = []
    if settings.secret_key in _KNOWN_BAD_SECRETS or len(settings.secret_key) < 32:
        reasons.append("default_secret")
    if settings.admin_password in _KNOWN_BAD_PASSWORDS:
        reasons.append("default_password")
    if not settings.cookie_secure and not settings.dev_mode:
        reasons.append("insecure_cookie")
    return {"defaults_in_use": bool(reasons), "reasons": reasons}
