"""Phase B: conversion cache invalidation on re-upload."""
from __future__ import annotations

from pathlib import Path


def test_invalidate_clears_directory(tmp_path: Path, monkeypatch):
    """Calling invalidate_book_cache deletes the directory and frees bytes."""
    from alejandria.config import get_settings

    monkeypatch.setenv("ALEJANDRIA_CACHES_PATH", str(tmp_path))
    get_settings.cache_clear()

    from alejandria.services.conversion_cache import cache_dir_for_book, invalidate_book_cache

    d = cache_dir_for_book(42)
    d.mkdir(parents=True)
    (d / "book.epub").write_bytes(b"x" * 100)

    freed = invalidate_book_cache(42)
    assert freed == 100
    assert not d.exists()


def test_invalidate_missing_is_noop(tmp_path: Path, monkeypatch):
    """Invalidating a book with no cache returns 0 and does not raise."""
    from alejandria.config import get_settings

    monkeypatch.setenv("ALEJANDRIA_CACHES_PATH", str(tmp_path))
    get_settings.cache_clear()

    from alejandria.services.conversion_cache import invalidate_book_cache

    freed = invalidate_book_cache(99)
    assert freed == 0
