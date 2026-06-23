"""Test fixtures."""

import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test env vars before importing app
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "alejandria-test-shared.db")
# Remove a stale DB from a previous test run.
if os.path.exists(_TEST_DB_PATH):
    try:
        os.remove(_TEST_DB_PATH)
    except OSError:
        pass
os.environ["ALEJANDRIA_SECRET_KEY"] = "test-secret-key-for-testing-only-do-not-ship"  # noqa: S105
os.environ["ALEJANDRIA_ALLOW_INSECURE_DEFAULTS"] = "true"
os.environ["ALEJANDRIA_DB_PATH"] = _TEST_DB_PATH
os.environ["ALEJANDRIA_LIBRARY_PATH"] = "/tmp/alejandria-test-library"
os.environ["ALEJANDRIA_CONFIG_PATH"] = "/tmp/alejandria-test-config"
os.environ["ALEJANDRIA_ADMIN_PASSWORD"] = "testpass"  # noqa: S105
os.environ["ALEJANDRIA_DEV_MODE"] = "true"
os.environ["ALEJANDRIA_COOKIE_SECURE"] = "false"  # TestClient is plain HTTP
os.environ["ALEJANDRIA_SCRAPER_OUTPUT_DIR"] = "/tmp/alejandria-test-scrapes"
os.environ["ALEJANDRIA_SCRAPER_ADAPTERS_FILE"] = "/tmp/alejandria-test-adapters.yaml"

from alejandria.db import Base, get_db
from alejandria.models import user  # noqa: F401
from alejandria.models import (  # noqa: F401
    annotation,
    highlight,
    oidc_state,
    progress,
    scrape_job,
    session,
    shelf,
)


@pytest.fixture(scope="session")
def engine():
    """In-memory SQLite engine for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db(engine):
    """Per-test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from alejandria.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def scraper_manager():
    """A ScraperManager with the browser lazy-loaded but not started — for
    unit tests. Use monkeypatch to skip the Playwright init."""
    from alejandria.services.scraper.manager import ScraperManager

    m = ScraperManager()
    m._browser = None  # ensure lazy
    return m
