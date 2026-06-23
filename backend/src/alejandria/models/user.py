"""User model."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alejandria.db import Base

if TYPE_CHECKING:
    from alejandria.models.session import UserSession


class UserRole(str, PyEnum):
    """User role hierarchy."""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class User(Base):
    """Application user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # Profile
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    # Permissions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_download: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_edit_metadata: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # OIDC link
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    oidc_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Reader preferences
    reader_theme: Mapped[str] = mapped_column(String(16), default="light", nullable=False)
    reader_font_size: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    reader_line_height: Mapped[float] = mapped_column(default=1.6, nullable=False)
    reader_font_family: Mapped[str] = mapped_column(String(64), default="serif", nullable=False)

    # Kindle email (for send-to-kindle)
    kindle_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    sessions: Mapped[list[UserSession]] = relationship(  # type: ignore[name-defined]
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
