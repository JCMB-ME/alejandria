"""Calibre DB service tests."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from alejandria.services.calibre_db import CalibreDB


@pytest.fixture
def calibre_db():
    """Create an in-memory Calibre DB with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Ensure the library directory exists and contains a mock book file
    library_path = Path("/tmp/alejandria-test-library")
    library_path.mkdir(parents=True, exist_ok=True)
    book_file_path = library_path / "Jane Doe" / "Test Book (1)"
    book_file_path.mkdir(parents=True, exist_ok=True)
    with open(book_file_path / "test.epub", "w") as f:
        f.write("dummy epub content")

    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            sort_title TEXT,
            timestamp TIMESTAMP,
            pubdate TIMESTAMP,
            series_index REAL,
            has_cover INTEGER DEFAULT 0,
            cover TEXT,
            path TEXT
        );
        CREATE TABLE authors (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            sort TEXT
        );
        CREATE TABLE books_authors_link (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            author INTEGER NOT NULL
        );
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE books_tags_link (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            tag INTEGER NOT NULL
        );
        CREATE TABLE series (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            sort TEXT
        );
        CREATE TABLE books_series_link (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            series INTEGER NOT NULL
        );
        CREATE TABLE data (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            format TEXT NOT NULL,
            uncompressed_size INTEGER,
            name TEXT,
            mtime TIMESTAMP
        );
        CREATE TABLE identifiers (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            type TEXT NOT NULL,
            val TEXT NOT NULL
        );
        CREATE TABLE languages (
            id INTEGER PRIMARY KEY,
            lang_code TEXT NOT NULL
        );
        CREATE TABLE books_languages_link (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            lang_code INTEGER NOT NULL
        );
        CREATE TABLE publishers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE books_publishers_link (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            publisher INTEGER NOT NULL
        );
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            text TEXT
        );

        INSERT INTO books (id, title, sort_title, has_cover, path)
            VALUES (1, 'Test Book', 'Test Book', 1, 'Jane Doe/Test Book (1)');
        INSERT INTO authors (id, name, sort)
            VALUES (1, 'Jane Doe', 'Doe, Jane');
        INSERT INTO books_authors_link (id, book, author)
            VALUES (1, 1, 1);
        INSERT INTO data (id, book, format, uncompressed_size, name)
            VALUES (1, 1, 'EPUB', 1024, 'test');
    """)
    conn.commit()
    conn.close()

    db = CalibreDB(db_path=db_path)
    yield db
    db_path.unlink()
    try:
        import shutil
        shutil.rmtree(library_path, ignore_errors=True)
    except Exception:
        pass


def test_count_books(calibre_db):
    assert calibre_db.count_books() == 1


def test_get_book(calibre_db):
    book = calibre_db.get_book(1)
    assert book is not None
    assert book["title"] == "Test Book"
    assert len(book["authors"]) == 1
    assert book["authors"][0].name == "Jane Doe"
    assert len(book["formats"]) == 1
    assert book["formats"][0].fmt == "EPUB"


def test_list_books(calibre_db):
    books, total = calibre_db.list_books()
    assert total == 1
    assert len(books) == 1
    assert books[0].id == 1
    assert books[0].title == "Test Book"


def test_get_book_file_path(calibre_db):
    path = calibre_db.get_book_file_path(1, "EPUB")
    assert path is not None
    assert "test.epub" in str(path)
