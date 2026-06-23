"""Phase C3: cover LRU cache."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from alejandria.services import cover


@pytest.fixture
def fake_cover_dir(tmp_path: Path, monkeypatch):
    """Point caches_path at tmp; pre-create a cover file for book_id=42."""
    monkeypatch.setenv("ALEJANDRIA_CACHES_PATH", str(tmp_path))
    from alejandria.config import get_settings

    get_settings.cache_clear()

    cover_dir = tmp_path / "covers" / "42"
    cover_dir.mkdir(parents=True)
    (cover_dir / "800.jpg").write_bytes(b"\xff\xd8\xff\xe0fake_jpeg")
    yield tmp_path
    get_settings.cache_clear()


def test_cached_cover_path_hits_on_second_call(fake_cover_dir: Path):
    """Second call for the same (book_id, size) does not re-stat the disk."""
    cover._cached_cover_path.cache_clear()

    # First call: cold.
    p1 = cover._cached_cover_path(42, "medium")
    assert p1 is not None and p1.exists()
    cache_info_after_first = cover._cached_cover_path.cache_info()
    assert cache_info_after_first.hits == 0

    # Patch Path.exists to verify the second call doesn't touch the disk.
    with patch.object(Path, "exists", autospec=True) as mock_exists:
        p2 = cover._cached_cover_path(42, "medium")
        # If the function re-runs (cache miss), mock_exists would have been called.
        assert mock_exists.call_count == 0
    assert p2 == p1
    cache_info_after_second = cover._cached_cover_path.cache_info()
    assert cache_info_after_second.hits == 1


def test_cached_cover_path_returns_none_when_missing(fake_cover_dir: Path):
    """A book without a cached cover returns None and caches that fact."""
    cover._cached_cover_path.cache_clear()
    assert cover._cached_cover_path(99999, "medium") is None
    # Second call: still None, no disk re-stat.
    with patch.object(Path, "exists", autospec=True) as mock_exists:
        assert cover._cached_cover_path(99999, "medium") is None
        assert mock_exists.call_count == 0


def test_get_cover_speedup(fake_cover_dir: Path):
    """get_cover() returns <1ms on the cached path for a 1KB file."""
    cover._cached_cover_path.cache_clear()
    # Warmup
    cover.get_cover(42, "medium")

    start = time.perf_counter()
    for _ in range(1000):
        data = cover.get_cover(42, "medium")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert data is not None
    assert elapsed_ms < 100, f"1000 cached get_cover calls took {elapsed_ms:.1f}ms"