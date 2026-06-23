"""Phase C2: shelf summary batching."""

from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from alejandria.services.calibre_db import CalibreDB


@pytest.fixture
def calibre_with_100_books():
    """1k-book library; the test requests summaries for 100 specific ids."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, sort_title TEXT,
            timestamp TIMESTAMP, pubdate TIMESTAMP, series_index REAL,
            has_cover INTEGER DEFAULT 0, cover TEXT, path TEXT
        );
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort TEXT);
        CREATE TABLE books_authors_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, author INTEGER NOT NULL
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE books_tags_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL
        );
        CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort TEXT);
        CREATE TABLE books_series_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, series INTEGER NOT NULL
        );
        CREATE TABLE data (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, format TEXT NOT NULL,
            uncompressed_size INTEGER, name TEXT, mtime TIMESTAMP
        );
    """)
    for i in range(1, 1001):
        conn.execute(
            "INSERT INTO books VALUES (?, ?, ?, NULL, NULL, 1.0, 0, NULL, ?)",
            (i, f"Book {i}", f"Book {i:04d}", f"path/{i}"),
        )
        conn.execute(
            "INSERT INTO authors VALUES (?, ?, ?)",
            (i, f"Author {i}", f"Author {i}"),
        )
        conn.execute(
            "INSERT INTO books_authors_link VALUES (?, ?, ?)",
            (i, i, i),
        )
        conn.execute(
            "INSERT INTO series VALUES (?, ?, ?)",
            (i, f"Series {i}", f"Series {i}"),
        )
        conn.execute(
            "INSERT INTO books_series_link VALUES (?, ?, ?)",
            (i, i, i),
        )
        conn.execute(
            "INSERT INTO data VALUES (?, ?, ?, ?, ?, NULL)",
            (i, i, "EPUB", 1024, f"file_{i}.epub"),
        )
    conn.commit()
    conn.close()

    db = CalibreDB(db_path=db_path)
    yield db
    db_path.unlink()


def test_get_books_summaries_under_100ms(calibre_with_100_books: CalibreDB):
    """100 summaries should resolve in <100 ms."""
    db = calibre_with_100_books
    ids = list(range(1, 101))

    # Warmup
    db.get_books_summaries(ids[:10])

    start = time.perf_counter()
    summaries = db.get_books_summaries(ids)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(summaries) == 100
    for s in summaries:
        assert s.id in ids
        assert s.title.startswith("Book ")
    assert elapsed_ms < 100, f"get_books_summaries took {elapsed_ms:.1f}ms"


def test_get_books_summaries_preserves_input_order(calibre_with_100_books: CalibreDB):
    """Output order matches input order, even with non-sorted ids."""
    db = calibre_with_100_books
    ids = [42, 17, 99, 1, 50]
    summaries = db.get_books_summaries(ids)
    assert [s.id for s in summaries] == ids


def test_get_books_summaries_handles_empty_input(calibre_with_100_books: CalibreDB):
    """Empty input returns empty list without a DB round-trip."""
    db = calibre_with_100_books
    assert db.get_books_summaries([]) == []


def test_get_books_summaries_handles_missing_ids(calibre_with_100_books: CalibreDB):
    """IDs not in the DB are skipped, present IDs keep their order."""
    db = calibre_with_100_books
    summaries = db.get_books_summaries([1, 9999, 2])
    assert [s.id for s in summaries] == [1, 2]