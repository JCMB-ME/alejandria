"""Reading progress tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from alejandria.db import Base


class ReadingProgress(Base):
    """Per-user reading position for a book."""

    __tablename__ = "reading_progress"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Calibre book id

    # Position (CFI for EPUB, page for PDF, etc.)
    position: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    position_type: Mapped[str] = mapped_column(String(16), default="cfi", nullable=False)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Reading session stats
    last_read_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Cumulative time in seconds
    total_reading_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Device tracking
    device_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Progress u={self.user_id} b={self.book_id} {self.progress_pct:.0%}>"
