"""Ebook format conversion via Calibre CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

from alejandria.config import get_settings
from alejandria.services.calibre_db import get_calibre_db
from alejandria.utils.log import get_logger

logger = get_logger(__name__)

# Formats that can be rendered directly in browser (no conversion needed)
BROWSER_NATIVE_FORMATS = {"EPUB", "PDF", "HTML", "TXT", "RTF", "FB2", "CBZ", "CBR"}

# Formats that need server-side conversion to a browser-native format
CONVERSION_TARGETS = {
    "MOBI": "EPUB",
    "AZW3": "EPUB",
    "AZW": "EPUB",
    "LIT": "EPUB",
    "LRF": "EPUB",
    "DJVU": "PDF",
    "DOCX": "EPUB",
    "DOC": "EPUB",
    "ODT": "EPUB",
    "HTMLZ": "EPUB",
}


def is_browser_native(fmt: str) -> bool:
    return fmt.upper() in BROWSER_NATIVE_FORMATS


def get_target_format(fmt: str) -> str:
    """Get the target format to convert to for browser rendering."""
    return CONVERSION_TARGETS.get(fmt.upper(), "EPUB")


def converted_cache_path(book_id: int, target_fmt: str) -> Path:
    """Path to cached converted file."""
    settings = get_settings()
    return settings.caches_path / "conversions" / str(book_id) / f"book.{target_fmt.lower()}"


async def convert(
    book_id: int,
    source_fmt: str,
    target_fmt: str | None = None,
    *,
    force: bool = False,
) -> Path | None:
    """Convert a book to a target format using Calibre's ebook-convert.

    Returns path to converted file, or None on failure.
    """
    if not get_settings().enable_calibre:
        logger.warning("conversion_disabled")
        return None

    target = target_fmt or get_target_format(source_fmt)
    cache = converted_cache_path(book_id, target)
    if cache.exists() and not force:
        return cache

    calibre = get_calibre_db()
    src = calibre.get_format_path(book_id, source_fmt)
    if not src or not src.exists():
        logger.error("source_file_not_found", book_id=book_id, fmt=source_fmt)
        return None

    cache.parent.mkdir(parents=True, exist_ok=True)

    calibre_bin = get_settings().calibre_bin_path
    ebook_convert_bin = calibre_bin.replace("calibredb", "ebook-convert")
    cmd = [
        ebook_convert_bin,
        str(src),
        str(cache),
        # Conservative flags for fast, quality conversion
        "--enable-heuristics",
        "--unsmarten-punctuation",
        "--disable-font-rescaling",
    ]

    # Format-specific flags
    if target.upper() == "EPUB":
        cmd.extend(["--epub-version", "3"])
    elif target.upper() == "PDF":
        cmd.extend(["--paper-size", "letter", "--pdf-default-font-size", "12"])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            logger.error(
                "conversion_failed",
                book_id=book_id,
                source=source_fmt,
                target=target,
                stderr=stderr.decode("utf-8", errors="ignore")[:2000],
            )
            return None
        if cache.exists():
            logger.info("conversion_done", book_id=book_id, target=target, size=cache.stat().st_size)
            return cache
    except TimeoutError:
        logger.error("conversion_timeout", book_id=book_id)
    except FileNotFoundError:
        logger.error("ebook_convert_not_found")
    except Exception as e:
        logger.exception("conversion_error", book_id=book_id, error=str(e))
    return None


async def get_readable_file(book_id: int, preferred_fmt: str | None = None) -> tuple[str, Path] | None:
    """Get a file ready for the reader.

    If the source format is browser-native, returns it directly.
    Otherwise, converts to target format.
    Returns (mime_type, path).
    """
    calibre = get_calibre_db()
    if preferred_fmt:
        path = calibre.get_format_path(book_id, preferred_fmt)
        if path and path.exists():
            return (_fmt_to_mime(preferred_fmt), path)

    # Iterate formats, pick best browser-native
    book = calibre.get_book(book_id)
    if not book:
        return None

    formats = book.get("formats", [])
    if not formats:
        return None

    # Prefer browser-native in order: EPUB > PDF > HTML > TXT > ...
    preferred_order = ["EPUB", "PDF", "HTML", "TXT", "FB2", "RTF", "CBZ", "CBR"]
    fmt_by_name = {f.fmt.upper(): f for f in formats}

    for fmt in preferred_order:
        if fmt in fmt_by_name:
            path = calibre.get_format_path(book_id, fmt)
            if path and path.exists():
                return (_fmt_to_mime(fmt), path)

    # Need to convert
    first = formats[0]
    source_fmt = first.fmt
    target = get_target_format(source_fmt)
    converted = await convert(book_id, source_fmt, target)
    if converted:
        return (_fmt_to_mime(target), converted)
    return None


def _fmt_to_mime(fmt: str) -> str:
    return {
        "EPUB": "application/epub+zip",
        "PDF": "application/pdf",
        "HTML": "text/html",
        "TXT": "text/plain",
        "FB2": "application/x-fictionbook+xml",
        "RTF": "application/rtf",
        "CBZ": "application/vnd.comicbook+zip",
        "CBR": "application/vnd.comicbook-rar",
    }.get(fmt.upper(), "application/octet-stream")
