"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alejandria.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    type_annotation_map: dict[Any, Any] = {}


def _ensure_db_path() -> None:
    """Ensure the database directory exists."""
    settings = get_settings()
    db_path = settings.db_path
    if str(db_path) == ":memory:":
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _make_engine() -> Engine:
    """Create the SQLAlchemy engine."""
    _ensure_db_path()
    settings = get_settings()
    db_url = f"sqlite:///{settings.db_path}"

    engine = create_engine(
        db_url,
        echo=settings.dev_mode,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        """Set SQLite pragmas for performance and integrity."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


engine: Engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Idempotent."""
    # Import all models to register them
    from alejandria.models import (  # noqa: F401
        annotation,
        highlight,
        progress,
        scrape_job,
        session,
        shelf,
        user,
    )

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine_cache() -> None:
    """Reset engine cache (for testing)."""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
