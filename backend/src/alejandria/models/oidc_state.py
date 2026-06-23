"""OIDC state parameter — persists CSRF tokens for the auth flow."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from alejandria.db import Base


class OIDCState(Base):
    """Short-lived (10 min) record of OIDC state tokens.

    Phase E will use this to verify the OIDC callback. For now, Phase B
    ships the table + cleanup logic so existing OIDC users can start
    populating rows without an immediate migration.
    """

    __tablename__ = "oidc_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    redirect_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<OIDCState state={self.state[:8]}...>"
