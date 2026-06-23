"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
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
    """Apply Alembic migrations to bring the schema up to head.

    Idempotent: if the database already matches the current head revision,
    this is a no-op.

    Falls back to ``Base.metadata.create_all`` only when ``alembic.ini`` is
    missing (a fresh checkout before `alembic init` has run). For installs
    that pre-date Alembic (v0.1.0), the DB has the model tables but no
    ``alembic_version`` row; we stamp the baseline revision so subsequent
    migrations don't try to re-apply it.
    """
    # Import all models to register them on the metadata.
    import structlog

    from alejandria.models import (  # noqa: F401
        annotation,
        highlight,
        oidc_state,
        progress,
        scrape_job,
        session,
        shelf,
        user,
    )
    log = structlog.get_logger(__name__)

    # Resolve alembic.ini relative to the project root.
    backend_root = Path(__file__).resolve().parents[2]  # backend/src/alejandria/db.py → backend/
    ini_path = backend_root / "alembic.ini"
    if not ini_path.exists():
        # Fresh checkout before `alembic init` ran: fall back to create_all.
        # This branch should not happen in a released image, but makes
        # local hacking less brittle.
        log.warning("alembic_ini_missing_falling_back_to_create_all")
        Base.metadata.create_all(bind=engine)
        return

    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(ini_path))
    cfg.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{get_settings().db_path}",
    )

    # If the DB already had tables from pre-Alembic v0.1.0, stamp the
    # baseline so the upgrade doesn't try to re-create existing tables.
    if "alembic_version" not in existing_tables and existing_tables:
        versions_dir = backend_root / "alembic" / "versions"
        baseline_revs = sorted(p.stem.split("_")[0] for p in versions_dir.glob("*.py"))
        if baseline_revs:
            log.info("stamping_pre_alembic_db", baseline=baseline_revs[0])
            command.stamp(cfg, baseline_revs[0])

    log.info("running_alembic_upgrade", db_path=str(get_settings().db_path))
    command.upgrade(cfg, "head")

    # Force the global engine to point at the freshly-migrated DB. This
    # matters in tests where a previous test mutated ALEJANDRIA_DB_PATH
    # via monkeypatch — both the settings cache and the engine must be
    # rebuilt so the next call site reads from the current env.
    get_settings.cache_clear()
    reset_engine_cache()


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
