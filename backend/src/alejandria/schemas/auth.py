"""Authentication & user schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from alejandria.models.user import UserRole


class UserBase(BaseModel):
    """Common user fields."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr | None = None
    display_name: str | None = None
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    """Create user payload."""

    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Update user payload (admin-only fields gated separately)."""

    username: str | None = Field(default=None, min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr | None = None
    display_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    can_download: bool | None = None
    can_edit_metadata: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    """User as returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    can_download: bool
    can_edit_metadata: bool
    is_anonymous: bool
    locale: str
    timezone: str
    avatar_url: str | None
    kindle_email: str | None
    reader_theme: str
    reader_font_size: int
    reader_line_height: float
    reader_font_family: str
    created_at: datetime
    last_login_at: datetime | None


class LoginRequest(BaseModel):
    """Login payload."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Public registration payload (only if enabled)."""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class SetupStatus(BaseModel):
    """First-time setup status — drives the SPA's login vs register screen."""

    needs_setup: bool
    user_count: int
    allow_registration: bool = False


class TokenResponse(BaseModel):
    """Login response with access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
    csrf_token: str
