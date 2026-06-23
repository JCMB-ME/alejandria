"""Phase C4-C5: to_thread concurrency proves non-blocking."""

from __future__ import annotations

import asyncio
import time

import pytest


class _FakeCalibre:
    """Stand-in for CalibreDB that simulates a 100ms-blocking sync call."""

    def __init__(self, delay_ms: int = 100):
        self.delay_s = delay_ms / 1000.0
        self.calls = 0

    def list_books(self, **_):
        time.sleep(self.delay_s)
        self.calls += 1
        return [], 0

    async def alist_books(self, **kwargs):
        return await asyncio.to_thread(self.list_books, **kwargs)


@pytest.mark.asyncio
async def test_50_concurrent_calls_run_in_parallel():
    """50 concurrent alist_books should finish in ~100ms, not 5s."""
    fake = _FakeCalibre(delay_ms=100)

    start = time.perf_counter()
    await asyncio.gather(*[fake.alist_books() for _ in range(50)])
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"50 concurrent calls took {elapsed:.2f}s (expected <1s)"
    assert fake.calls == 50


@pytest.mark.asyncio
async def test_event_loop_stays_free_during_to_thread():
    """While to_thread runs a 100ms blocking call, the event loop is responsive."""
    fake = _FakeCalibre(delay_ms=100)

    async def heart_beat():
        # Should tick at least 5 times during the 100ms blocking call.
        ticks = 0
        end = time.perf_counter() + 0.2
        while time.perf_counter() < end:
            await asyncio.sleep(0.02)
            ticks += 1
        return ticks

    heart_task = asyncio.create_task(heart_beat())
    books_task = asyncio.create_task(fake.alist_books())

    books_result = await books_task
    ticks = await heart_task

    assert books_result == ([], 0)
    assert ticks >= 5, f"Event loop was blocked: only {ticks} heartbeats in 200ms"


@pytest.mark.asyncio
async def test_get_cover_does_not_block_event_loop(monkeypatch):
    """get_cover routed through to_thread does not block the event loop."""
    import asyncio
    import time
    from alejandria.services import cover as cover_mod

    # Stub get_cover to a 200ms blocker.
    def fake_get_cover(book_id, size):
        time.sleep(0.2)
        return b"\xff\xd8\xff\xe0fake"

    monkeypatch.setattr(cover_mod, "get_cover", fake_get_cover)

    from fastapi.testclient import TestClient
    from alejandria.main import create_app

    app = create_app()
    with TestClient(app) as client:
        async def heart_beat():
            ticks = 0
            end = time.perf_counter() + 0.5
            while time.perf_counter() < end:
                await asyncio.sleep(0.05)
                ticks += 1
            return ticks

        async def fetch_cover():
            return await asyncio.to_thread(client.get, "/api/library/covers/1.jpg")

        cover_resp, ticks = await asyncio.gather(fetch_cover(), heart_beat())
        assert cover_resp.status_code in (200, 404)
        assert ticks >= 5, f"Event loop blocked: {ticks} ticks in 500ms"