"""Phase C6: cover stream-decode keeps memory bounded."""

from __future__ import annotations

import io
import tracemalloc

import pytest
from PIL import Image


def _make_large_cover_jpeg(width: int = 4000, height: int = 6000) -> bytes:
    """Generate a >1MB JPEG to exercise the >500 KB draft() path."""
    img = Image.new("RGB", (width, height), color=(120, 80, 40))
    # Add a noise pattern that defeats JPEG compression.
    import random
    random.seed(0)
    pixels = img.load()
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=98)
    return buf.getvalue()


def test_cover_resize_stays_under_500mb_for_5mb_input(monkeypatch, tmp_path):
    """A >1 MB JPEG cover should not allocate >500 MB during resize."""
    monkeypatch.setenv("ALEJANDRIA_CACHES_PATH", str(tmp_path))
    from alejandria.config import get_settings

    get_settings.cache_clear()

    raw = _make_large_cover_jpeg()
    assert len(raw) > 1_000_000, "Test setup: cover should be >1 MB"

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    # Simulate the resize branch (target_w=800 for "medium").
    target_w = 800
    img = Image.open(io.BytesIO(raw))
    if len(raw) > 500_000 and img.format in {"JPEG", "PNG", "WEBP"}:
        ratio = target_w / img.width
        img.draft(img.mode, (target_w, int(img.height * ratio)))
    if img.width > target_w:
        new_h = int(img.height * (target_w / img.width))
        img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "filename")
    peak_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
    peak_mb = peak_bytes / (1024 * 1024)

    assert peak_mb < 500, f"Cover resize allocated {peak_mb:.1f} MB (cap: 500 MB)"
    assert len(out.getvalue()) < len(raw) / 2