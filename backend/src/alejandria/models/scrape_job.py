"""Scrape job model (URL -> PDF/EPUB/CBZ web scraper)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from alejandria.db import Base


class ScrapeJobStatus(str, PyEnum):
    """Lifecycle states for a scrape job."""

    QUEUED = "queued"
    SCRAPING = "scraping"
    PACKAGING = "packaging"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScrapeJob(Base):
    """A user's request to scrape a URL into one or more formats."""

    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Source
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    adapter_name: Mapped[str] = mapped_column(String(64), default="generic", nullable=False)

    # Requested formats and destinations
    formats_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    destinations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Lifecycle
    status: Mapped[ScrapeJobStatus] = mapped_column(
        Enum(ScrapeJobStatus), default=ScrapeJobStatus.QUEUED, nullable=False, index=True
    )

    # Progress
    total_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_page: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Failure
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outputs (JSON-encoded dicts: {"PDF": "/config/scrapes/1/out.pdf", ...})
    output_paths_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_book_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ScrapeJob {self.id} u={self.user_id} {self.status.value}>"
