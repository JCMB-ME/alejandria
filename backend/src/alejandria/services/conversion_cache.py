"""Helpers for managing the per-book conversion cache."""

from __future__ import annotations

import shutil
from pathlib import Path

from alejandria.config import get_settings


def cache_dir_for_book(book_id: int) -> Path:
    """Directory holding all cached conversions for a book."""
    return get_settings().caches_path / "conversions" / str(book_id)


def invalidate_book_cache(book_id: int) -> int:
    """Delete all cached conversions for a book.

    Returns the number of bytes freed. Idempotent.
    """
    d = cache_dir_for_book(book_id)
    if not d.exists():
        return 0
    total = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
    shutil.rmtree(d, ignore_errors=True)
    return total
