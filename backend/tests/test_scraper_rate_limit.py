"""Tests for the per-user job rate limiter."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from alejandria.models.scrape_job import ScrapeJob, ScrapeJobStatus
from alejandria.models.user import User, UserRole
from alejandria.services.scraper.rate_limit import JobRateLimiter


def _make_user(db: Session, name: str) -> User:
    u = User(
        username=name,
        role=UserRole.USER,
        is_active=True,
        can_download=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_job(db: Session, user_id: int) -> ScrapeJob:
    j = ScrapeJob(
        user_id=user_id,
        url="https://example.com/1",
        adapter_name="generic",
        formats_json='["PDF"]',
        destinations_json='["download"]',
        status=ScrapeJobStatus.QUEUED,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def test_allows_under_limit(db: Session):
    user = _make_user(db, "alice")
    for _ in range(5):
        _make_job(db, user.id)
    JobRateLimiter(max_jobs_per_hour=10).check(db, user.id)  # no raise


def test_blocks_at_limit(db: Session):
    user = _make_user(db, "bob")
    for _ in range(10):
        _make_job(db, user.id)
    with pytest.raises(HTTPException) as exc:
        JobRateLimiter(max_jobs_per_hour=10).check(db, user.id)
    assert exc.value.status_code == 429
    assert "Rate limit" in exc.value.detail


def test_does_not_block_other_user(db: Session):
    alice = _make_user(db, "alice2")
    bob = _make_user(db, "bob2")
    for _ in range(10):
        _make_job(db, alice.id)
    JobRateLimiter(max_jobs_per_hour=10).check(db, bob.id)  # no raise
