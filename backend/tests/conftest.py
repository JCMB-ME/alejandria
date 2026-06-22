"""Test fixtures."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test env vars before importing app
os.environ["ALEJANDRIA_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ALEJANDRIA_DB_PATH"] = ":memory:"
os.environ["ALEJANDRIA_LIBRARY_PATH"] = "/tmp/alejandria-test-library"
os.environ["ALEJANDRIA_CONFIG_PATH"] = "/tmp/alejandria-test-config"
os.environ["ALEJANDRIA_ADMIN_PASSWORD"] = "testpass"
os.environ["ALEJANDRIA_DEV_MODE"] = "true"

from alejandria.db import Base, get_db
from alejandria.models import user  # noqa: F401


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
