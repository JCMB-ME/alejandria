"""Public security status endpoint — drives the SPA's default-credentials banner."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.config import get_settings
from alejandria.db import get_db
from alejandria.models import User

router = APIRouter()

_KNOWN_BAD_SECRETS = frozenset({
    "change-me-in-production-please",
    "change-me-to-a-long-random-string",
    "changeme",
    "",
})


@router.get("/status")
async def security_status(
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Returns whether the instance is using well-known default values.

    No secrets are exposed — only a list of which defaults are in use.
    The SPA renders a yellow banner when any are.

    The admin password is intentionally NOT checked here: in the
    first-time-setup flow, `ALEJANDRIA_ADMIN_PASSWORD` is empty on purpose
    so the SPA's /register page can create the first admin. The actual
    admin password lives in the users table (hashed), and the admin
    changes it from the user-management UI, not by editing .env. We
    therefore can't tell from config alone whether the admin's real
    password is "default" — and we shouldn't flag an empty env field as
    one.
    """
    settings = get_settings()
    reasons: list[str] = []

    # Secret key: real, config-driven. Genuine default or too short → warn.
    if settings.secret_key in _KNOWN_BAD_SECRETS or len(settings.secret_key) < 32:
        reasons.append("default_secret")

    # Insecure-defaults override: only present in dev. Worth flagging because
    # it disables the password/secret validators — easy to forget and ship.
    if settings.allow_insecure_defaults:
        reasons.append("insecure_defaults_override")

    # Cookie security: in dev (HTTP) cookies aren't secure, that's fine.
    # In prod (HTTPS) they must be — flag if not.
    if not settings.cookie_secure and not settings.dev_mode:
        reasons.append("insecure_cookie")

    # Bootstrap user count: if there are no users yet, the SPA will route
    # to /register. The banner's "default password" wording would be
    # confusing in that state, so the SPA can suppress the banner based
    # on this count if it wants.
    user_count = db.scalar(select(User.id).limit(1))
    has_users = user_count is not None

    return {
        "defaults_in_use": bool(reasons),
        "reasons": reasons,
        "has_users": has_users,
    }
