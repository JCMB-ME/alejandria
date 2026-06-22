"""Library scanner — watches for new/removed books."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from alejandria.config import get_settings
from alejandria.services.calibre_db import get_calibre_db

from alejandria.utils.log import get_logger
logger = get_logger(__name__)


class LibraryScanner:
    """Watches the library directory and updates Calibre metadata.db.

    Uses the `calibredb` CLI to add new books (more reliable than direct DB
    manipulation, which would require duplicating Calibre's normalization logic).
    """

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._last_scan: datetime | None = None
        self._scanning = False
        self._library_root = get_settings().library_path

    def start(self) -> None:
        """Start watching the library directory."""
        if self._observer:
            return
        self._library_root.mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        handler = _LibraryEventHandler(self)
        try:
            self._loop = asyncio.get_running_loop()
            handler.set_loop(self._loop)
        except RuntimeError:
            # No running loop yet — the handler will fall back to sync
            pass
        self._observer.schedule(handler, str(self._library_root), recursive=True)
        self._observer.start()
        # Record the initial scan time so /api/library/stats has a real value
        # before the first manual rescan or library change.
        self._last_scan = datetime.now(timezone.utc)
        logger.info("library_scanner_started", path=str(self._library_root))

    def stop(self) -> None:
        """Stop watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("library_scanner_stopped")

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    @property
    def last_scan(self) -> datetime | None:
        return self._last_scan

    def trigger_rescan(self) -> asyncio.Task:
        """Trigger a full library rescan."""
        return asyncio.create_task(self._rescan())

    async def _rescan(self) -> dict[str, Any]:
        """Run calibredb check_library to validate and refresh."""
        with self._lock:
            if self._scanning:
                return {"status": "already_scanning"}
            self._scanning = True

        settings = get_settings()
        calibre_bin = settings.calibre_bin_path

        result: dict[str, Any] = {
            "status": "started",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # calibredb check_library validates and rebuilds the FTS index
            cmd = [calibre_bin.replace("calibredb", "calibredb"), "check_library",
                   "--library-path", str(self._library_root)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            result["exit_code"] = proc.returncode
            result["stdout"] = stdout.decode("utf-8", errors="ignore")[:2000]
            result["stderr"] = stderr.decode("utf-8", errors="ignore")[:2000]
            result["status"] = "completed" if proc.returncode == 0 else "error"
            self._last_scan = datetime.now(timezone.utc)
        except FileNotFoundError:
            result["status"] = "calibre_not_found"
            result["error"] = f"calibredb not found at {calibre_bin}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        finally:
            self._scanning = False

        logger.info("library_rescan_done", **result)
        return result

    async def add_book(self, file_path: Path) -> dict[str, Any]:
        """Add a single book to the library.

        Uses ``--automerge overwrite`` so that re-importing the same URL
        (a common case for the scraper, which may produce duplicate runs)
        updates the format on the existing record instead of failing with
        "ya existen en la base de datos". In that case ``calibredb add``
        prints the resolved book id on stdout ("ID de libros añadidos: N"),
        but the actual book we matched is the existing one — its id appears
        in the stderr preamble of the same line.
        """
        settings = get_settings()
        calibre_bin = settings.calibre_bin_path
        cmd = [
            calibre_bin.replace("calibredb", "calibredb"), "add",
            "--automerge", "overwrite",
            "--library-path", str(self._library_root),
            str(file_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore"),
            }
        except FileNotFoundError:
            return {"exit_code": -1, "error": "calibredb not found"}

    async def remove_book(self, book_id: int) -> bool:
        """Remove a book from the library."""
        settings = get_settings()
        calibre_bin = settings.calibre_bin_path
        cmd = [
            calibre_bin.replace("calibredb", "calibredb"), "remove",
            "--library-path", str(self._library_root),
            str(book_id),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def update_metadata(self, book_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Update metadata for a book in the library using calibredb."""
        settings = get_settings()
        calibre_bin = settings.calibre_bin_path
        cmd = [
            calibre_bin.replace("calibredb", "calibredb"), "set_metadata",
            "--library-path", str(self._library_root),
        ]
        for key, val in fields.items():
            if val is None:
                val = ""
            cmd.extend(["-f", f"{key}:{val}"])
        cmd.append(str(book_id))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore"),
            }
        except FileNotFoundError:
            return {"exit_code": -1, "error": "calibredb not found"}


class _LibraryEventHandler(FileSystemEventHandler):
    """File system event handler for the library directory."""

    def __init__(self, scanner: LibraryScanner) -> None:
        self.scanner = scanner
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop to schedule async tasks on from the watchdog thread."""
        self._loop = loop

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        
        # ONLY auto-import files that are dropped directly in the library root folder.
        # This prevents infinite loops and double-imports when calibredb writes/renames files in library subfolders.
        if path.parent.resolve() != self.scanner._library_root.resolve():
            return

        if any(part.startswith(".") for part in path.parts) or ".caltrash" in path.parts or ".calnotes" in path.parts:
            return
        if path.suffix.lower() in {".epub", ".pdf", ".mobi", ".azw3", ".azw",
                                    ".fb2", ".djvu", ".rtf", ".docx", ".txt",
                                    ".html", ".htmlz", ".lit", ".lrf", ".odt",
                                    ".cbz", ".cbr"}:
            logger.info("library_file_added", path=str(path))
            if self._loop and not self._loop.is_closed():
                # Schedule from the watchdog thread onto the main event loop
                asyncio.run_coroutine_threadsafe(
                    self.scanner.add_book(path), self._loop
                )
            else:
                # Fallback: run synchronously via subprocess
                import subprocess
                settings = get_settings()
                cmd = [
                    settings.calibre_bin_path, "add",
                    "--library-path", str(self.scanner._library_root),
                    str(path),
                ]
                try:
                    subprocess.run(cmd, check=False, timeout=60)
                except Exception as e:
                    logger.error("scanner_add_failed", path=str(path), error=str(e))

    def on_deleted(self, event: FileSystemEvent) -> None:
        logger.info("library_file_deleted", path=event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # Treat as delete + create. watchdog exposes dest_path on FileMovedEvent
        # but the base FileSystemEvent does not — build a synthetic event.
        if not event.is_directory:
            dest = getattr(event, "dest_path", None) or getattr(event, "dest", None)
            if not dest:
                return
            from watchdog.events import FileCreatedEvent
            self.on_created(FileCreatedEvent(dest))


_scanner: LibraryScanner | None = None


def get_scanner() -> LibraryScanner:
    global _scanner  # noqa: PLW0603
    if _scanner is None:
        _scanner = LibraryScanner()
    return _scanner
