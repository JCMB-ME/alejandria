"""Tests for ScraperManager crash recovery on startup."""

from __future__ import annotations

import json
import pytest
from sqlalchemy.orm import Session, sessionmaker

from alejandria.models.scrape_job import ScrapeJob, ScrapeJobStatus
from alejandria.models.user import User, UserRole
from alejandria.services.scraper import manager as mgr_module
from alejandria.services.scraper.manager import ScraperManager


def _make_user(db: Session, name: str = "tester") -> User:
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


def _make_job(db: Session, user_id: int, status: ScrapeJobStatus) -> ScrapeJob:
    j = ScrapeJob(
        user_id=user_id,
        url="https://example.com/1",
        adapter_name="generic",
        formats_json=json.dumps(["PDF"]),
        destinations_json=json.dumps(["download"]),
        status=status,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


@pytest.fixture
def patch_session_local(engine, monkeypatch):
    """Make the global SessionLocal() in the manager module point at the test engine."""
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(mgr_module, "SessionLocal", TestSession)
    return TestSession


@pytest.fixture
def clean_scrape_jobs(db):
    """Clear the scrape_jobs table before the test so assertions are stable."""
    db.query(ScrapeJob).delete()
    db.commit()
    return db


def test_recover_orphaned_jobs_marks_scraping_as_failed(db, engine, patch_session_local, clean_scrape_jobs):
    u = _make_user(db, "alice_mgr")
    _make_job(db, u.id, ScrapeJobStatus.SCRAPING)
    _make_job(db, u.id, ScrapeJobStatus.PACKAGING)
    _make_job(db, u.id, ScrapeJobStatus.QUEUED)  # should NOT be touched

    sm = ScraperManager()
    sm._recover_orphaned_jobs()

    Session_ = patch_session_local
    with Session_() as s:
        rows = s.query(ScrapeJob).all()
        by_status: dict[str, list[ScrapeJob]] = {}
        for r in rows:
            by_status.setdefault(r.status.value, []).append(r)
        assert len(by_status.get("failed", [])) == 2
        for r in by_status["failed"]:
            assert r.error == "Server restarted while job was running"
        # Queued is left alone
        assert len(by_status.get("queued", [])) == 1
