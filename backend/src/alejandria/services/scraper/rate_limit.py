"""Per-user job rate limiter for the scraper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alejandria.config import get_settings
from alejandria.models.scrape_job import ScrapeJob


class JobRateLimiter:
    """Counts scrape jobs a user has created in the last hour."""

    def __init__(self, max_jobs_per_hour: int | None = None) -> None:
        if max_jobs_per_hour is None:
            max_jobs_per_hour = get_settings().scraper_max_jobs_per_hour
        self.max_jobs_per_hour = max_jobs_per_hour

    def check(self, db: Session, user_id: int) -> None:
        """Raise HTTPException(429) if the user has >= N jobs in the last hour."""
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        stmt = (
            select(func.count(ScrapeJob.id))
            .where(ScrapeJob.user_id == user_id, ScrapeJob.created_at >= cutoff)
        )
        count = db.execute(stmt).scalar_one()
        if count >= self.max_jobs_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded; max {self.max_jobs_per_hour} "
                    f"jobs / hour"
                ),
            )
