"""Settings router — user preferences and app info."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import require_admin
from alejandria.auth.security import hash_password
from alejandria.config import get_settings
from alejandria.db import get_db
from alejandria.models.user import User
from alejandria.schemas.auth import UserCreate, UserRead, UserUpdate

router = APIRouter()


@router.get("/app")
async def app_info() -> dict:
    """Get public app info (no secrets)."""
    from alejandria import __version__

    settings = get_settings()
    return {
        "version": __version__,
        "oidc_enabled": settings.oidc_enabled,
        "registration_enabled": False,  # TODO: settings flag
        "smtp_configured": bool(settings.smtp_host and settings.smtp_username),
        "calibre_enabled": settings.enable_calibre,
    }


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> list[User]:
    users = db.execute(select(User).order_by(User.username)).scalars().all()
    return users


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    existing = db.execute(
        select(User).where(
            (User.username == payload.username) | (User.email == payload.email)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User with that username/email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)

    # Detect security-sensitive changes so we can kill sessions after.
    kills_sessions = False
    if "is_active" in data and data["is_active"] is False:
        kills_sessions = True
    if "role" in data and data["role"] != user.role:
        kills_sessions = True
    if "password" in data and data["password"]:
        kills_sessions = True

    for k, v in data.items():
        if k == "password" and v:
            user.password_hash = hash_password(v)
        else:
            setattr(user, k, v)

    if kills_sessions:
        # Audit log: who was demoted/disabled. Phase E adds a structured
        # AuditLog table; for now, log via structlog so it lands in stdout.
        from alejandria.utils.log import get_logger
        logger = get_logger(__name__)
        logger.warning(
            "user_mutated_sessions_revoked",
            target_user_id=user.id,
            actor_user_id=admin.id,
            changes={k: v for k, v in data.items() if k in {"is_active", "role", "password"}},
        )
        # Delete all sessions for the affected user.
        from alejandria.models.session import UserSession
        db.execute(
            UserSession.__table__.delete().where(UserSession.user_id == user.id)
        )

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
