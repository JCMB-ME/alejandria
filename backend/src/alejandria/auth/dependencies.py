"""FastAPI authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.security import decode_token, hash_token
from alejandria.db import get_db
from alejandria.models.session import UserSession
from alejandria.models.user import User, UserRole

# OAuth2 scheme — token URL is /api/auth/login
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


def _extract_token(request: Request, bearer_token: str | None) -> str | None:
    """Extract token from Authorization header or cookie."""
    if bearer_token:
        return bearer_token
    # Check cookie
    cookie_token = request.cookies.get("alejandria_session")
    if cookie_token:
        return cookie_token
    return None


def _get_user_from_session(db: Session, token: str) -> User | None:
    """Resolve a user from a JWT token.

    Looks up the matching UserSession row (token_hash + expires_at) so that
    logout, password change, and admin "disable user" actually invalidate
    the session. The UserSession table was created for this purpose
    (models/session.py) but never consulted before Phase A.
    """
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", "0"))
    except (jwt.PyJWTError, ValueError, TypeError):
        return None

    if not user_id:
        return None

    th = hash_token(token)
    sess = db.execute(
        select(UserSession).where(
            UserSession.token_hash == th,
            UserSession.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()
    if sess is None:
        return None

    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def revoke_session(db: Session, token: str) -> bool:
    """Delete the UserSession row matching this token. Returns True if a row was deleted."""
    th = hash_token(token)
    sess = db.execute(
        select(UserSession).where(UserSession.token_hash == th)
    ).scalar_one_or_none()
    if sess is None:
        return False
    db.delete(sess)
    db.commit()
    return True


def get_optional_user(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Get the current user if authenticated, else None (for public endpoints)."""
    token = _extract_token(request, bearer_token)
    if not token:
        return None
    return _get_user_from_session(db, token)


def get_current_user(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Require an authenticated user. Raises 401 otherwise."""
    token = _extract_token(request, bearer_token)
    user = _get_user_from_session(db, token) if token else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_or_401(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Like get_current_user but raises 401 with a custom detail.

    The OPDS router uses this so it can return a message that names OPDS
    specifically (not the generic auth message).
    """
    token = _extract_token(request, bearer_token)
    user = _get_user_from_session(db, token) if token else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OPDS requires authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an admin user."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def require_role(*roles: UserRole):
    """Require a specific role or set of roles."""

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in roles)}",
            )
        return user

    return _checker


def touch_session(db: Session, user: User) -> None:
    """Update last_active_at for user's sessions (rate-limited)."""
    now = datetime.now(UTC)
    for sess in user.sessions:
        if (now - sess.last_active_at).total_seconds() > 60:
            sess.last_active_at = now
