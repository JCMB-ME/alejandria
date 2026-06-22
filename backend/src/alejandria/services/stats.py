"""Reading stats and analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alejandria.models.progress import ReadingProgress
from alejandria.models.user import User
from alejandria.schemas.book import LibraryStats


class StatsService:
    """Compute reading statistics for a user."""

    def user_overview(self, db: Session, user_id: int) -> dict:
        """Top-level stats for the dashboard."""
        progress_q = db.execute(
            select(ReadingProgress).where(ReadingProgress.user_id == user_id)
        ).scalars().all()

        total_books_started = len(progress_q)
        books_finished = sum(1 for p in progress_q if p.progress_pct >= 0.95)
        currently_reading = sum(
            1 for p in progress_q
            if 0.01 < p.progress_pct < 0.95
        )
        total_seconds = sum(p.total_reading_time for p in progress_q)

        return {
            "total_books_started": total_books_started,
            "books_finished": books_finished,
            "currently_reading": currently_reading,
            "total_reading_time_seconds": total_seconds,
            "total_reading_time_hours": round(total_seconds / 3600, 1),
            "average_finish_pct": (
                round(sum(p.progress_pct for p in progress_q) / len(progress_q) * 100, 1)
                if progress_q else 0
            ),
        }

    def reading_streak(self, db: Session, user_id: int) -> dict:
        """Current and longest reading streak (consecutive days)."""
        # Get distinct days when user read
        days = db.execute(
            select(func.date(ReadingProgress.last_read_at))
            .where(ReadingProgress.user_id == user_id)
            .distinct()
            .order_by(func.date(ReadingProgress.last_read_at).desc())
        ).scalars().all()

        if not days:
            return {"current_streak": 0, "longest_streak": 0}

        day_dates = [datetime.strptime(str(d), "%Y-%m-%d").date() for d in days]
        today = datetime.now(timezone.utc).date()

        # Current streak
        current = 0
        cursor = today
        if day_dates and day_dates[0] >= today - timedelta(days=1):
            cursor = day_dates[0]
            for d in day_dates:
                if d == cursor:
                    current += 1
                    cursor = cursor - timedelta(days=1)
                elif d < cursor:
                    break

        # Longest streak
        longest = 1
        run = 1
        for i in range(1, len(day_dates)):
            if (day_dates[i - 1] - day_dates[i]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

        return {"current_streak": current, "longest_streak": longest}

    def reading_by_year(self, db: Session, user_id: int) -> dict[int, int]:
        """Books finished per year."""
        rows = db.execute(
            select(
                func.extract("year", ReadingProgress.finished_at).label("year"),
                func.count("*").label("count"),
            )
            .where(ReadingProgress.user_id == user_id)
            .where(ReadingProgress.finished_at.isnot(None))
            .group_by("year")
            .order_by("year")
        ).all()
        return {int(r.year): r.count for r in rows}

    def daily_reading(self, db: Session, user_id: int, days: int = 30) -> list[dict]:
        """Daily reading minutes for the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # Approximate: count progress updates per day as proxy
        rows = db.execute(
            select(
                func.date(ReadingProgress.last_read_at).label("day"),
                func.sum(ReadingProgress.total_reading_time).label("seconds"),
            )
            .where(ReadingProgress.user_id == user_id)
            .where(ReadingProgress.last_read_at >= cutoff)
            .group_by("day")
            .order_by("day")
        ).all()
        return [{"date": str(r.day), "minutes": round((r.seconds or 0) / 60, 1)} for r in rows]
