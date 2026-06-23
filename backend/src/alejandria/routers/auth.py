"""Authentication router."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user, revoke_session
from alejandria.auth.oidc import OIDCClient
from alejandria.auth.rate_limit import check_login_rate_limit, record_login_attempt
from alejandria.auth.security import (
    create_access_token,
    generate_csrf_token,
    hash_password,
    hash_token,
    verify_password,
)
from alejandria.config import get_settings
from alejandria.db import get_db
from alejandria.models.session import UserSession
from alejandria.models.user import User, UserRole
from alejandria.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SetupStatus,
    TokenResponse,
    UserRead,
    UserUpdate,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Login via OAuth2 password flow (form-encoded)."""
    retry_after = check_login_rate_limit(db, request)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    record_login_attempt(db, request)

    user = db.execute(
        select(User).where(User.username == form.username)
    ).scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return _issue_token(response, db, user, user_agent=form.client_id or "")


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Login via JSON body (for SPA)."""
    retry_after = check_login_rate_limit(db, request)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    record_login_attempt(db, request)

    user = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return _issue_token(response, db, user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Logout: invalidate the current session."""
    token = request.cookies.get("alejandria_session") or ""
    revoke_session(db, token)
    response.delete_cookie("alejandria_session")
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
async def get_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Get current user."""
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Update current user (limited fields)."""
    # Users can update display name, email, password, reader preferences, username
    allowed = {"username", "email", "display_name", "password", "kindle_email",
               "reader_theme", "reader_font_size", "reader_line_height", "reader_font_family"}
    data = payload.model_dump(exclude_unset=True)

    # Check if username is being changed and is already taken
    if "username" in data and data["username"] is not None and data["username"] != user.username:
        existing_user = db.execute(
            select(User).where(User.username == data["username"])
        ).scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

    for field in ("role", "is_active", "can_download", "can_edit_metadata"):
        data.pop(field, None)
    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "password" and v:
            user.password_hash = hash_password(v)
        else:
            setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(db: Annotated[Session, Depends(get_db)]) -> SetupStatus:
    """First-time setup probe — drives login vs register screen on the SPA."""
    count = db.scalar(select(User.id).limit(1))
    user_count = 1 if count is not None else 0
    return SetupStatus(
        needs_setup=user_count == 0,
        user_count=user_count,
        allow_registration=user_count == 0,  # public registration only while empty
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Public registration.

    - If no users exist yet, this is the first-time setup: the new user is
      created as ADMIN and is auto-logged-in.
    - If users already exist, registration is locked (admins create accounts
      from the user management UI).
    """
    existing = db.scalar(select(User.id).limit(1))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Contact the admin.",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role=UserRole.ADMIN,  # first user is always admin
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Seed the default shelves (Currently Reading, Finished, Wishlist, Favorites)
    # so the new admin has the same baseline as the env-var-driven bootstrap.
    from alejandria.utils.bootstrap import _create_default_shelves
    _create_default_shelves(db, user.id)

    return _issue_token(response, db, user)


# OIDC endpoints ---------------------------------------------------------------

@router.get("/oidc/login")
async def oidc_login(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Get OIDC authorization URL."""
    if not OIDCClient().enabled:
        raise HTTPException(status_code=400, detail="OIDC not configured")
    state = OIDCClient.generate_state()
    # TODO: persist state in cache/session for CSRF
    url = await OIDCClient().get_authorization_url(state)
    return {"authorization_url": url, "state": state}


# Helpers ---------------------------------------------------------------------

def _issue_token(
    response: Response,
    db: Session,
    user: User,
    *,
    user_agent: str = "",
) -> TokenResponse:
    """Generate a JWT, persist a session, and set the cookie."""
    settings = get_settings()
    token = create_access_token(user.id)
    csrf = generate_csrf_token()

    sess = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=csrf,
        user_agent=user_agent[:512] if user_agent else None,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_lifetime),
    )
    db.add(sess)

    user.last_login_at = datetime.now(UTC)
    db.commit()

    response.set_cookie(
        key="alejandria_session",
        value=token,
        max_age=settings.session_lifetime,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="alejandria_csrf",
        value=csrf,
        max_age=settings.session_lifetime,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.session_lifetime,
        user=UserRead.model_validate(user),
        csrf_token=csrf,
    )
