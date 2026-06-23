"""Annotation model (notes attached to highlights)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from alejandria.db import Base


class Annotation(Base):
    """A note attached to a highlight or position."""

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Optional link to highlight
    highlight_id: Mapped[int | None] = mapped_column(
        ForeignKey("highlights.id", ondelete="CASCADE"), nullable=True
    )

    # Optional direct position (for note-without-highlight)
    cfi: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_private: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
