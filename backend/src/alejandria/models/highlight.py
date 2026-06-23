"""Highlight model (passages marked by user)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from alejandria.db import Base


class Highlight(Base):
    """A user highlight in a book."""

    __tablename__ = "highlights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Position
    cfi: Mapped[str] = mapped_column(String(512), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Color / style. The column is String(7) to enforce a "#RRGGBB"
    # hex format — legacy named tokens (yellow/green/blue/pink/orange)
    # are translated to hex in the migration that introduces this column.
    color: Mapped[str] = mapped_column(String(7), default="#FFEB3B", nullable=False)
    style: Mapped[str] = mapped_column(String(32), default="highlight", nullable=False)  # highlight|underline|note

    # Free-text note attached by the user. Null when the user has not
    # written anything. UI handles null gracefully (textarea shows the
    # placeholder and saves an empty string on blur only when the user
    # actually typed something).
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chapter context
    chapter: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Highlight u={self.user_id} b={self.book_id} {self.text[:30]!r}>"
