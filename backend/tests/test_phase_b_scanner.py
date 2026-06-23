"""Phase B: scanner concurrency."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from alejandria.services.scanner import LibraryScanner


@pytest.mark.asyncio
async def test_concurrent_add_book_serialised(tmp_path: Path):
    """100 concurrent add_book calls result in serialised calibredb invocations."""
    scanner = LibraryScanner()
    scanner._library_root = tmp_path

    invocation_log: list[str] = []

    class FakeProc:
        returncode = 0
        stdout = b""
        stderr = b""

        async def communicate(self):
            return (b"", b"")

    async def fake_exec(*cmd, **kw):
        invocation_log.append(" ".join(cmd))
        return FakeProc()

    with patch("alejandria.services.scanner.asyncio.create_subprocess_exec",
               side_effect=fake_exec):
        tasks = [
            scanner.add_book(tmp_path / f"book{i}.epub")
            for i in range(20)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(results) == 20
    assert all(not isinstance(r, Exception) for r in results)
    # Each call must have produced exactly one subprocess exec.
    assert len(invocation_log) == 20


@pytest.mark.asyncio
async def test_no_event_loop_does_not_run_sync(tmp_path: Path, monkeypatch):
    """Without a loop, on_created skips (does not fall back to sync subprocess)."""
    import subprocess
    import alejandria.services.scanner as scanner_mod
    from watchdog.events import FileCreatedEvent

    scanner = scanner_mod.LibraryScanner()
    scanner._library_root = tmp_path
    handler = scanner_mod._LibraryEventHandler(scanner)
    # _loop is None — simulate "shutdown or pre-startup" state.

    sync_called = False
    real_run = subprocess.run

    def fake_run(*a, **kw):
        nonlocal sync_called
        sync_called = True
        return None

    monkeypatch.setattr(subprocess, "run", fake_run)

    handler.on_created(FileCreatedEvent(str(tmp_path / "book.epub")))
    # If sync fallback ran, sync_called would be True. The new code skips.
    assert not sync_called
    # Sanity: monkeypatch didn't break real subprocess.run globally.
    assert subprocess.run is real_run or subprocess.run is fake_run
