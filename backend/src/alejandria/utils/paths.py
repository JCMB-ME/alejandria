"""Path utilities."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def safe_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    # Remove path separators and control chars
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Truncate
    return name[:240] or "untitled"


def book_path(library_root: Path, book_id: int, fmt: str) -> Path:
    """Get the file path for a book in the Calibre library structure.

    Calibre stores books as: Author/Title (id)/Title - id.fmt
    This is a fallback; actual path is queried from Calibre metadata.db.
    """
    return library_root / f"{book_id}.{fmt.lower()}"


def calibre_path_from_row(library_root: Path, name: str, book_id: int) -> Path:
    """Construct a book file path from the Calibre `data` table row.

    The 'name' column in the `data` table is the path relative to library root,
    e.g., "Author Name/Book Title (1234)/Book Title - BookId.epub".
    """
    return library_root / name


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def humanize_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    if size_bytes < 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_dir_size(path: Path) -> int:
    """Get total size of a directory."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total
