"""Phase B: Alembic + schema completeness tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from alejandria.config import get_settings
from alejandria.db import Base, init_db, reset_engine_cache
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


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    """Point Settings at a fresh tmp DB and reset the engine cache."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ALEJANDRIA_DB_PATH", str(db_file))
    get_settings.cache_clear()
    reset_engine_cache()
    yield db_file
    # monkeypatch restores ALEJANDRIA_DB_PATH automatically; init_db()
    # calls reset_engine_cache() at the end of every alembic run, so
    # the next test's lifespan will rebuild the engine against the
    # restored env var.


def test_alembic_baseline_creates_all_tables(fresh_db: Path):
    """alembic upgrade head on a fresh DB creates every model table."""
    from alembic import command
    from alembic.config import Config
    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{fresh_db}")
    command.upgrade(cfg, "head")

    inspector = inspect(create_engine(f"sqlite:///{fresh_db}"))
    tables = set(inspector.get_table_names())

    # Every model's table must exist.
    expected = {table.name for table in Base.metadata.tables.values()}
    assert expected <= tables, f"Missing tables: {expected - tables}"

    # Alembic bookkeeping must be present.
    assert "alembic_version" in tables


def test_init_db_is_idempotent(fresh_db: Path):
    """init_db() can be called twice without raising."""
    init_db()
    init_db()  # second call must not fail
    inspector = inspect(create_engine(f"sqlite:///{fresh_db}"))
    assert "alembic_version" in inspector.get_table_names()


def test_schema_completeness(fresh_db: Path):
    """Every column declared in a model exists as an actual table column."""
    init_db()
    inspector = inspect(create_engine(f"sqlite:///{fresh_db}"))
    for table_name, table in Base.metadata.tables.items():
        model_cols = {c.name for c in table.columns}
        actual_cols = {c["name"] for c in inspector.get_columns(table_name)}
        missing = model_cols - actual_cols
        assert not missing, f"Table {table_name} missing columns: {missing}"


def test_upgrade_from_v010_stamps_baseline(tmp_path: Path, monkeypatch):
    """A DB that has the v0.1.0 tables but no alembic_version gets stamped."""
    # Simulate v0.1.0: create_all on a fresh DB, then drop alembic_version.
    db_file = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=legacy_engine)
    with legacy_engine.begin() as conn:
        # If Alembic had ever run, this row would exist.
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    legacy_engine.dispose()

    monkeypatch.setenv("ALEJANDRIA_DB_PATH", str(db_file))
    get_settings.cache_clear()
    reset_engine_cache()

    init_db()  # must stamp the baseline, not crash

    inspector = inspect(create_engine(f"sqlite:///{db_file}"))
    assert "alembic_version" in inspector.get_table_names()
