"""Calibre metadata.db reader.

We read Calibre's metadata.db directly via sqlite3 — no Calibre Python module
required. This means we can:
- Read Calibre libraries without the Calibre app installed
- Ship a much smaller Docker image
- Avoid the GPL-3 contamination (we only USE Calibre, we don't link it)

Schema reference: https://manual.calibre-ebook.com/develop.html#the-catalog-api
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alejandria.config import get_settings
from alejandria.schemas.book import (
    BookAuthor,
    BookDetail,
    BookFormat,
    BookSummary,
    LibraryStats,
    SeriesInfo,
    TagInfo,
)
from alejandria.utils.log import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Calibre metadata.db schema
# ---------------------------------------------------------------------------
# Main tables we read from:
#   books         (id, title, sort_title, timestamp, pubdate, series_index,
#                  author_sort, isbn, lccn, flags, has_cover, cover)
#   authors       (id, name, sort, link)
#   books_authors_link (id, book, author)
#   tags          (id, name)
#   books_tags_link (id, book, tag)
#   series        (id, name, sort)
#   books_series_link (id, book, series)
#   data          (id, book, format, uncompressed_size, name, mtime)
#   comments      (id, book, text)
#   identifiers   (id, book, type, val)
#   languages     (id, lang_code)
#   books_languages_link (id, book, lang_code)
#   publishers    (id, name)
#   books_publishers_link (id, book, publisher)
#   ratings       (id, rating)   -- integer 0-10 typically divided by 2 for stars


# Format ext mapping (Calibre `format` is the UPPER extension)
FORMAT_EXT_MAP: dict[str, str] = {
    "EPUB": "epub",
    "PDF": "pdf",
    "MOBI": "mobi",
    "AZW3": "azw3",
    "AZW": "azw",
    "FB2": "fb2",
    "DJVU": "djvu",
    "LIT": "lit",
    "LRF": "lrf",
    "RTF": "rtf",
    "DOCX": "docx",
    "DOC": "doc",
    "HTML": "html",
    "HTMLZ": "htmlz",
    "TXT": "txt",
    "ODT": "odt",
    "CBZ": "cbz",
    "CBR": "cbr",
}


class CalibreDB:
    """Read Calibre metadata.db directly.

    Thread-safe; uses per-call connections (SQLite is fast for this).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path or get_settings().calibre_metadata_db
        self._cached_columns: dict[str, set[str]] | None = None

    def _available_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        """Return column names for a table (cached)."""
        if self._cached_columns is None:
            self._cached_columns = {}
        if table not in self._cached_columns:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            self._cached_columns[table] = {r[1] for r in rows}
        return self._cached_columns[table]

    def _safe_select(self, conn: sqlite3.Connection, table: str, fields: list[str]) -> str:
        """Build a SELECT clause with only fields that exist in the table."""
        cols = self._available_columns(conn, table)
        safe = [f for f in fields if f in cols and "." not in f]
        if not safe:
            safe = ["id"]
        return ", ".join(f"{table}.{f}" for f in safe)

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def exists(self) -> bool:
        return self._db_path.exists()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Get a connection to the Calibre DB.

        Yields an in-memory connection with a minimal schema if the file is
        missing or empty. This lets the rest of the API function before any
        books are added.
        """
        with self._lock:
            # Ensure file exists
            if not self._db_path.exists():
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                sqlite3.connect(self._db_path).close()

            # Try to open read-only first
            try:
                conn = sqlite3.connect(
                    f"file:{self._db_path}?mode=ro",
                    uri=True,
                    timeout=30,
                    check_same_thread=False,
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only = ON")
                # Check schema exists
                conn.execute("SELECT 1 FROM books LIMIT 1").fetchone()
            except sqlite3.OperationalError:
                # Schema missing — fall back to an in-memory empty DB
                if "conn" in locals():
                    conn.close()
                conn = sqlite3.connect(":memory:")
                conn.row_factory = sqlite3.Row
                _ensure_minimal_schema(conn)

            try:
                yield conn
            finally:
                conn.close()

    # -----------------------------------------------------------------------
    # Books
    # -----------------------------------------------------------------------
    def iter_books(
        self,
        *,
        fields: list[str] | None = None,
        order_by: str = "sort_title",
        descending: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over all books.

        Each yielded dict contains the requested fields plus a list of related
        metadata (authors, tags, series, formats).
        """
        fields = fields or [
            "id", "title", "sort_title", "author_sort", "timestamp",
            "pubdate", "series_index", "has_cover", "cover",
            "isbn", "lccn", "uuid", "flags", "last_modified",
        ]
        with self.connect() as conn:
            cols = self._safe_select(conn, "books", fields)
            direction = "DESC" if descending else "ASC"
            available = self._available_columns(conn, "books")
            order_col = order_by if order_by in available else "title"
            sql = f"SELECT {cols} FROM books b ORDER BY {order_col} {direction}"
            cursor = conn.execute(sql)
            for row in cursor:
                book = dict(row)
                book_id = book["id"]
                # Attach related data
                book["authors"] = self._authors_for(conn, book_id)
                book["tags"] = self._tags_for(conn, book_id)
                book["series"] = self._series_for(conn, book_id)
                book["formats"] = self._formats_for(conn, book_id)
                book["identifiers"] = self._identifiers_for(conn, book_id)
                book["languages"] = self._languages_for(conn, book_id)
                book["publisher"] = self._publisher_for(conn, book_id)
                yield book

    def get_book(self, book_id: int) -> dict[str, Any] | None:
        """Get full metadata for one book."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if not row:
                return None
            book = dict(row)
            book["authors"] = self._authors_for(conn, book_id)
            book["tags"] = self._tags_for(conn, book_id)
            book["series"] = self._series_for(conn, book_id)
            book["formats"] = self._formats_for(conn, book_id)
            book["identifiers"] = self._identifiers_for(conn, book_id)
            book["languages"] = self._languages_for(conn, book_id)
            book["publisher"] = self._publisher_for(conn, book_id)
            book["comments"] = self._comments_for(conn, book_id)
            book["rating"] = self._rating_for(conn, book_id)
            return book

    def count_books(self) -> int:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) AS c FROM books").fetchone()
            return r["c"] if r else 0

    def list_books(
        self,
        *,
        page: int = 1,
        page_size: int = 24,
        search: str | None = None,
        author_id: int | None = None,
        tag_id: int | None = None,
        series_id: int | None = None,
        sort: str = "sort_title",
        order: str = "asc",
    ) -> tuple[list[BookSummary], int]:
        """List books with filters + pagination."""
        where: list[str] = []
        params: list[Any] = []
        joins: list[str] = []

        if search:
            where.append("(b.title LIKE ? OR a.name LIKE ?)")
            joins.append("LEFT JOIN books_authors_link bal ON bal.book = b.id")
            joins.append("LEFT JOIN authors a ON a.id = bal.author")
            like = f"%{search}%"
            params.extend([like, like])

        if author_id is not None:
            where.append("bal2.author = ?")
            if "books_authors_link bal" not in " ".join(joins):
                joins.append("LEFT JOIN books_authors_link bal2 ON bal2.book = b.id")
            params.append(author_id)

        if tag_id is not None:
            where.append("btl.tag = ?")
            joins.append("LEFT JOIN books_tags_link btl ON btl.book = b.id")
            params.append(tag_id)

        if series_id is not None:
            where.append("bsl.series = ?")
            joins.append("LEFT JOIN books_series_link bsl ON bsl.book = b.id")
            params.append(series_id)

        where_sql = "WHERE " + " AND ".join(where) if where else ""
        join_sql = " ".join(dict.fromkeys(joins))  # dedupe, preserve order

        allowed_sorts = {
            "id", "title", "sort_title", "timestamp", "pubdate", "last_modified",
            "series_index", "rating",
        }
        if sort not in allowed_sorts:
            sort = "sort_title"
        order = "DESC" if order.lower() == "desc" else "ASC"

        offset = (page - 1) * page_size

        # Get total + rows. Be defensive about sort column existence.
        with self.connect() as conn:
            available = self._available_columns(conn, "books")
            effective_sort = sort if sort in available else "title"
            count_sql = f"SELECT COUNT(DISTINCT b.id) AS total FROM books b {join_sql} {where_sql}"
            total = conn.execute(count_sql, params).fetchone()["total"]
            sql = (
                f"SELECT b.* FROM books b {join_sql} {where_sql} "
                f"GROUP BY b.id ORDER BY b.{effective_sort} {order} LIMIT ? OFFSET ?"
            )
            rows = conn.execute(sql, params + [page_size, offset]).fetchall()

        # Fetch related tables in ONE round-trip per table, keyed by the page's ids.
        # Previous version did 4 queries per book (24 books = 96 queries per page).
        book_ids = [row["id"] for row in rows]
        authors_by_book: dict[int, list] = {}
        tags_by_book: dict[int, list] = {}
        series_by_book: dict[int, Any] = {}
        formats_by_book: dict[int, list] = {}
        if book_ids:
            with self.connect() as conn:
                authors_by_book = self._authors_for_many(conn, book_ids)
                tags_by_book = self._tags_for_many(conn, book_ids)
                series_by_book = self._series_for_many(conn, book_ids)
                formats_by_book = self._formats_for_many(conn, book_ids)

        books: list[BookSummary] = []
        for row in rows:
            book = dict(row)
            bid = book["id"]
            book["authors"] = authors_by_book.get(bid, [])
            book["tags"] = tags_by_book.get(bid, [])
            book["series"] = series_by_book.get(bid)
            book["formats"] = formats_by_book.get(bid, [])
            books.append(self._to_summary(book))
        return books, total

    def search_books(self, query: str, limit: int = 50) -> list[BookSummary]:
        """Full-text-like search across title, authors, tags, series."""
        books, _ = self.list_books(search=query, page_size=limit)
        return books

    # -----------------------------------------------------------------------
    # Authors
    # -----------------------------------------------------------------------
    def list_authors(self) -> list[BookAuthor]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, sort FROM authors ORDER BY sort COLLATE NOCASE"
            ).fetchall()
        return [BookAuthor(id=r["id"], name=r["name"], sort=r["sort"]) for r in rows]

    def get_author(self, author_id: int) -> BookAuthor | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, name, sort FROM authors WHERE id = ?", (author_id,)
            ).fetchone()
        if not row:
            return None
        return BookAuthor(id=row["id"], name=row["name"], sort=row["sort"])

    def count_authors(self) -> int:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) AS c FROM authors").fetchone()
            return r["c"] if r else 0

    # -----------------------------------------------------------------------
    # Tags
    # -----------------------------------------------------------------------
    def list_tags(self) -> list[TagInfo]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, name FROM tags ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [TagInfo(id=r["id"], name=r["name"]) for r in rows]

    def count_tags(self) -> int:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) AS c FROM tags").fetchone()
            return r["c"] if r else 0

    # -----------------------------------------------------------------------
    # Series
    # -----------------------------------------------------------------------
    def list_series(self) -> list[SeriesInfo]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, sort FROM series ORDER BY sort COLLATE NOCASE"
            ).fetchall()
        return [SeriesInfo(id=r["id"], name=r["name"], sort=r["sort"]) for r in rows]

    def get_series(self, series_id: int) -> SeriesInfo | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, name, sort FROM series WHERE id = ?", (series_id,)
            ).fetchone()
        if not row:
            return None
        return SeriesInfo(id=row["id"], name=row["name"], sort=row["sort"])

    def count_series(self) -> int:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) AS c FROM series").fetchone()
            return r["c"] if r else 0

    def get_books_in_series(self, series_id: int) -> list[BookSummary]:
        books, _ = self.list_books(series_id=series_id, page_size=1000,
                                    sort="series_index", order="asc")
        return books

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------
    def get_stats(self, last_scan: datetime | None = None) -> LibraryStats:
        with self.connect() as conn:
            total_books = conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
            total_authors = conn.execute("SELECT COUNT(*) c FROM authors").fetchone()["c"]
            total_tags = conn.execute("SELECT COUNT(*) c FROM tags").fetchone()["c"]
            total_series = conn.execute("SELECT COUNT(*) c FROM series").fetchone()["c"]
            fmt_rows = conn.execute(
                "SELECT format, COUNT(*) c FROM data GROUP BY format"
            ).fetchall()
            formats = {r["format"]: r["c"] for r in fmt_rows}
            size_row = conn.execute(
                "SELECT COALESCE(SUM(uncompressed_size), 0) s FROM data"
            ).fetchone()
        return LibraryStats(
            total_books=total_books,
            total_authors=total_authors,
            total_tags=total_tags,
            total_series=total_series,
            total_size_bytes=size_row["s"] if size_row else 0,
            formats=formats,
            last_scan=last_scan or datetime.now(UTC),
        )

    def get_etag_token(self) -> str:
        """Stable token reflecting the library's mutation state.

        Used by routers to compute HTTP `ETag` headers. The token changes
        only when (a) a book is added/removed (total_books changes) or
        (b) the scanner completes a rescan (last_modified advances). Within
        the same library state, all requests see the same token.
        """
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
            available = self._available_columns(conn, "books")
            epoch = 0
            if "last_modified" in available:
                row = conn.execute(
                    "SELECT MAX(last_modified) m FROM books"
                ).fetchone()
                last_modified = row["m"] if row else None
                if last_modified:
                    try:
                        if "T" in last_modified:
                            dt = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
                        else:
                            dt = datetime.fromisoformat(last_modified)
                        epoch = int(dt.timestamp())
                    except (ValueError, TypeError):
                        epoch = 0
        return f"{total}-{epoch}"

    # -----------------------------------------------------------------------
    # Async wrappers (Phase C4): every public method consumed by an async
    # router is exposed as `a<method>` that delegates via asyncio.to_thread.
    # The underlying sync methods stay unchanged for non-async callers (tests,
    # alembic env, scanner iter_books).
    # -----------------------------------------------------------------------
    async def alist_books(self, **kwargs) -> tuple[list[BookSummary], int]:
        """Async wrapper around list_books."""
        return await asyncio.to_thread(self.list_books, **kwargs)

    async def aget_book(self, book_id: int) -> dict | None:
        return await asyncio.to_thread(self.get_book, book_id)

    async def acount_books(self) -> int:
        return await asyncio.to_thread(self.count_books)

    async def aget_stats(self, last_scan: datetime | None = None) -> LibraryStats:
        return await asyncio.to_thread(self.get_stats, last_scan)

    async def alist_authors(self) -> list[BookAuthor]:
        return await asyncio.to_thread(self.list_authors)

    async def aget_author(self, author_id: int) -> BookAuthor | None:
        return await asyncio.to_thread(self.get_author, author_id)

    async def alist_tags(self) -> list[TagInfo]:
        return await asyncio.to_thread(self.list_tags)

    async def alist_series(self) -> list[SeriesInfo]:
        return await asyncio.to_thread(self.list_series)

    async def aget_series(self, series_id: int) -> SeriesInfo | None:
        return await asyncio.to_thread(self.get_series, series_id)

    async def aget_books_summaries(self, book_ids: list[int]) -> list[BookSummary]:
        return await asyncio.to_thread(self.get_books_summaries, book_ids)

    async def aget_etag_token(self) -> str:
        return await asyncio.to_thread(self.get_etag_token)

    # -----------------------------------------------------------------------
    # File access
    # -----------------------------------------------------------------------
    def get_book_file_path(self, book_id: int, fmt: str | None = None) -> Path | None:
        """Get the absolute path to a book file in the library.

        Calibre's `data.name` is a generated file basename, but the real path
        is library/Author/Title (N)/name.ext. We find the file by globbing.
        """
        library = get_settings().library_path
        with self.connect() as conn:
            if fmt:
                row = conn.execute(
                    "SELECT name FROM data WHERE book = ? AND format = ? "
                    "ORDER BY id LIMIT 1",
                    (book_id, fmt.upper()),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT name, format FROM data WHERE book = ? "
                    "ORDER BY format LIMIT 1",
                    (book_id,),
                ).fetchone()
        if not row:
            return None
        target_name = row["name"]
        target_fmt = (fmt or row.get("format", "")).lower()
        # Search for the file in any subdirectory of the library
        if not library.exists():
            return None
        # Build the basename with or without extension
        ext = "." + target_fmt if target_fmt else ""
        # Strategy: walk library, find a file whose stem matches `name` and
        # extension matches the format.
        for path in library.rglob("*"):
            if not path.is_file():
                continue
            if path.stem == target_name or path.stem.startswith(target_name):
                if target_fmt and path.suffix.lower().lstrip(".") == target_fmt:
                    return path
                if not target_fmt:
                    return path
        # Fallback: any file with matching extension in the library
        if target_fmt:
            for path in library.rglob(f"*.{target_fmt}"):
                if path.is_file():
                    return path
        return None

    def get_format_path(self, book_id: int, fmt: str) -> Path | None:
        return self.get_book_file_path(book_id, fmt)

    def get_first_format(self, book_id: int) -> tuple[str, Path] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT format, name FROM data WHERE book = ? ORDER BY id LIMIT 1",
                (book_id,),
            ).fetchone()
        if not row:
            return None
        fmt = row["format"]
        path = self.get_book_file_path(book_id, fmt)
        if not path:
            return None
        return fmt, path

    # -----------------------------------------------------------------------
    # Internal: related data
    # -----------------------------------------------------------------------
    def _authors_for(self, conn: sqlite3.Connection, book_id: int) -> list[BookAuthor]:
        rows = conn.execute(
            "SELECT a.id, a.name, a.sort FROM authors a "
            "JOIN books_authors_link bal ON bal.author = a.id "
            "WHERE bal.book = ? ORDER BY bal.id",
            (book_id,),
        ).fetchall()
        return [BookAuthor(id=r["id"], name=r["name"], sort=r["sort"]) for r in rows]

    def _tags_for(self, conn: sqlite3.Connection, book_id: int) -> list[TagInfo]:
        rows = conn.execute(
            "SELECT t.id, t.name FROM tags t "
            "JOIN books_tags_link btl ON btl.tag = t.id "
            "WHERE btl.book = ? ORDER BY t.name",
            (book_id,),
        ).fetchall()
        return [TagInfo(id=r["id"], name=r["name"]) for r in rows]

    def _series_for(self, conn: sqlite3.Connection, book_id: int) -> SeriesInfo | None:
        row = conn.execute(
            "SELECT s.id, s.name, s.sort FROM series s "
            "JOIN books_series_link bsl ON bsl.series = s.id "
            "WHERE bsl.book = ?",
            (book_id,),
        ).fetchone()
        if not row:
            return None
        return SeriesInfo(id=row["id"], name=row["name"], sort=row["sort"])

    def _authors_for_many(
        self, conn: sqlite3.Connection, book_ids: list[int],
    ) -> dict[int, list[BookAuthor]]:
        if not book_ids:
            return {}
        placeholders = ",".join("?" for _ in book_ids)
        rows = conn.execute(
            f"SELECT bal.book AS book_id, a.id, a.name, a.sort "
            f"FROM authors a "
            f"JOIN books_authors_link bal ON bal.author = a.id "
            f"WHERE bal.book IN ({placeholders}) ORDER BY bal.id",
            book_ids,
        ).fetchall()
        out: dict[int, list[BookAuthor]] = {bid: [] for bid in book_ids}
        for r in rows:
            out[r["book_id"]].append(
                BookAuthor(id=r["id"], name=r["name"], sort=r["sort"])
            )
        return out

    def _tags_for_many(
        self, conn: sqlite3.Connection, book_ids: list[int],
    ) -> dict[int, list[TagInfo]]:
        if not book_ids:
            return {}
        placeholders = ",".join("?" for _ in book_ids)
        rows = conn.execute(
            f"SELECT btl.book AS book_id, t.id, t.name "
            f"FROM tags t "
            f"JOIN books_tags_link btl ON btl.tag = t.id "
            f"WHERE btl.book IN ({placeholders}) ORDER BY t.name",
            book_ids,
        ).fetchall()
        out: dict[int, list[TagInfo]] = {bid: [] for bid in book_ids}
        for r in rows:
            out[r["book_id"]].append(TagInfo(id=r["id"], name=r["name"]))
        return out

    def _series_for_many(
        self, conn: sqlite3.Connection, book_ids: list[int],
    ) -> dict[int, SeriesInfo]:
        if not book_ids:
            return {}
        placeholders = ",".join("?" for _ in book_ids)
        rows = conn.execute(
            f"SELECT bsl.book AS book_id, s.id, s.name, s.sort "
            f"FROM series s "
            f"JOIN books_series_link bsl ON bsl.series = s.id "
            f"WHERE bsl.book IN ({placeholders})",
            book_ids,
        ).fetchall()
        out: dict[int, SeriesInfo] = {}
        for r in rows:
            out[r["book_id"]] = SeriesInfo(
                id=r["id"], name=r["name"], sort=r["sort"],
            )
        return out

    def _formats_for_many(
        self, conn: sqlite3.Connection, book_ids: list[int],
    ) -> dict[int, list[BookFormat]]:
        if not book_ids:
            return {}
        placeholders = ",".join("?" for _ in book_ids)
        data_cols = self._available_columns(conn, "data")
        want = [c for c in ("format", "name", "uncompressed_size", "mtime") if c in data_cols]
        select = ", ".join(f"d.{c}" for c in want) if want else "d.format, d.name"
        rows = conn.execute(
            f"SELECT d.book AS book_id, {select} "
            f"FROM data d WHERE d.book IN ({placeholders}) ORDER BY d.format",
            book_ids,
        ).fetchall()
        out: dict[int, list[BookFormat]] = {bid: [] for bid in book_ids}
        for r in rows:
            mtime = None
            if "mtime" in r.keys() and r["mtime"]:
                try:
                    mtime = datetime.fromisoformat(r["mtime"])
                except (ValueError, TypeError):
                    pass
            out[r["book_id"]].append(
                BookFormat(
                    fmt=r["format"],
                    path=r["name"] if "name" in r.keys() and r["name"] else "",
                    size=r["uncompressed_size"] if "uncompressed_size" in r.keys() and r["uncompressed_size"] else 0,
                    mtime=mtime,
                )
            )
        return out

    def get_books_summaries(self, book_ids: list[int]) -> list[BookSummary]:
        """Batch-fetch summaries for an explicit list of book ids.

        Used by /api/shelves/{id} where the book_ids come from the app DB
        (ShelfBook or ReadingProgress) and we need lightweight summaries
        (no comments / rating / identifiers / publisher). One round-trip per
        related table — independent of `len(book_ids)` up to 100.
        """
        if not book_ids:
            return []
        # Preserve input order.
        order = {bid: i for i, bid in enumerate(book_ids)}
        with self.connect() as conn:
            available = self._available_columns(conn, "books")
            want = [c for c in (
                "id", "title", "sort_title", "pubdate", "series_index",
                "has_cover", "cover",
            ) if c in available]
            select = ", ".join(f"b.{c}" for c in want) if want else "b.*"
            placeholders = ",".join("?" for _ in book_ids)
            rows = conn.execute(
                f"SELECT {select} FROM books b WHERE b.id IN ({placeholders})",
                book_ids,
            ).fetchall()
            authors_by_book = self._authors_for_many(conn, book_ids)
            tags_by_book = self._tags_for_many(conn, book_ids)
            series_by_book = self._series_for_many(conn, book_ids)
            formats_by_book = self._formats_for_many(conn, book_ids)

        books_by_id: dict[int, BookSummary] = {}
        for row in rows:
            book = dict(row)
            bid = book["id"]
            book["authors"] = authors_by_book.get(bid, [])
            book["tags"] = tags_by_book.get(bid, [])
            book["series"] = series_by_book.get(bid)
            book["formats"] = formats_by_book.get(bid, [])
            books_by_id[bid] = self._to_summary(book)

        # Return summaries in the same order as the input.
        return [books_by_id[bid] for bid in book_ids if bid in books_by_id]

    def _formats_for(self, conn: sqlite3.Connection, book_id: int) -> list[BookFormat]:
        # Build query defensively based on actual columns
        data_cols = self._available_columns(conn, "data")
        want = [c for c in ("format", "name", "uncompressed_size", "mtime") if c in data_cols]
        select = ", ".join(want) if want else "format, name"
        rows = conn.execute(
            f"SELECT {select} FROM data WHERE book = ? ORDER BY format",
            (book_id,),
        ).fetchall()
        result: list[BookFormat] = []
        for r in rows:
            rdict = dict(r)
            mtime = None
            if rdict.get("mtime"):
                try:
                    mtime = datetime.fromisoformat(rdict["mtime"])
                except (ValueError, TypeError):
                    pass
            result.append(
                BookFormat(
                    fmt=rdict["format"],
                    path=rdict.get("name") or "",
                    size=rdict.get("uncompressed_size") or 0,
                    mtime=mtime,
                )
            )
        return result

    def _identifiers_for(self, conn: sqlite3.Connection, book_id: int) -> dict[str, str]:
        rows = conn.execute(
            "SELECT type, val FROM identifiers WHERE book = ?", (book_id,)
        ).fetchall()
        return {r["type"]: r["val"] for r in rows}

    def _languages_for(self, conn: sqlite3.Connection, book_id: int) -> list[str]:
        rows = conn.execute(
            "SELECT l.lang_code FROM languages l "
            "JOIN books_languages_link bll ON bll.lang_code = l.id "
            "WHERE bll.book = ?",
            (book_id,),
        ).fetchall()
        return [r["lang_code"] for r in rows]

    def _publisher_for(self, conn: sqlite3.Connection, book_id: int) -> str | None:
        row = conn.execute(
            "SELECT p.name FROM publishers p "
            "JOIN books_publishers_link bpl ON bpl.publisher = p.id "
            "WHERE bpl.book = ? LIMIT 1",
            (book_id,),
        ).fetchone()
        return row["name"] if row else None

    def _comments_for(self, conn: sqlite3.Connection, book_id: int) -> str | None:
        row = conn.execute(
            "SELECT text FROM comments WHERE book = ?", (book_id,)
        ).fetchone()
        return row["text"] if row else None

    def _rating_for(self, conn: sqlite3.Connection, book_id: int) -> int | None:
        # Two Calibre schemas exist: a `rating` column on books, or a
        # books_ratings_link table. Try the simpler one first.
        book_cols = self._available_columns(conn, "books")
        tables = set(self._cached_columns.keys()) if self._cached_columns else set()

        if "rating" in book_cols:
            row = conn.execute(
                "SELECT rating FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if row and row["rating"] is not None:
                return int(row["rating"]) // 2

        if "books_ratings_link" in tables and "ratings" in tables:
            row = conn.execute(
                "SELECT r.rating FROM books_ratings_link brl "
                "LEFT JOIN ratings r ON r.id = brl.rating "
                "WHERE brl.book = ?",
                (book_id,),
            ).fetchone()
            if row and row["rating"] is not None:
                return int(row["rating"]) // 2

        return None

    # -----------------------------------------------------------------------
    # Conversion: raw row → schema
    # -----------------------------------------------------------------------
    def _to_summary(self, book: dict) -> BookSummary:
        """Convert a Calibre row dict to BookSummary."""
        formats = book.get("formats", [])
        cover_path = None
        if book.get("has_cover"):
            cover_path = f"/api/library/covers/{book['id']}.jpg"
        return BookSummary(
            id=book["id"],
            title=book.get("title", ""),
            sort_title=book.get("sort_title"),
            authors=book.get("authors", []),
            tags=book.get("tags", []),
            series=book.get("series"),
            series_index=book.get("series_index"),
            languages=book.get("languages", []),
            pubdate=self._to_dt(book.get("pubdate")),
            publisher=book.get("publisher"),
            rating=book.get("rating"),
            cover_path=cover_path,
            has_cover=bool(book.get("has_cover")),
            formats=formats,
        )

    def _to_detail(self, book: dict) -> BookDetail:
        summary = self._to_summary(book)
        return BookDetail(
            **summary.model_dump(),
            description=book.get("comments"),
            comments=book.get("comments"),
            identifiers=book.get("identifiers", {}),
            timestamp=self._to_dt(book.get("timestamp")),
            last_modified=self._to_dt(book.get("last_modified")),
        )

    @staticmethod
    def _to_dt(value: Any) -> datetime | None:
        """Convert Calibre's date string to datetime."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # Calibre format: "2024-01-15 12:34:56+00:00" or ISO
            if "T" in value:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None


def ro_uri() -> str:
    """SQLite URI mode flag for read-only (legacy compatibility)."""
    return "ro"


def _ensure_minimal_schema(conn: sqlite3.Connection) -> None:
    """Create the minimal Calibre tables we read from.

    Only the columns we actually query are created. This lets the app
    function before the user has added any books via `calibredb add`.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            sort_title TEXT,
            timestamp TIMESTAMP,
            pubdate TIMESTAMP,
            series_index REAL DEFAULT 1.0,
            has_cover INTEGER DEFAULT 0,
            cover TEXT
        );
        CREATE TABLE IF NOT EXISTS authors (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort TEXT);
        CREATE TABLE IF NOT EXISTS books_authors_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, author INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS books_tags_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS series (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort TEXT);
        CREATE TABLE IF NOT EXISTS books_series_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, series INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS data (
            id INTEGER PRIMARY KEY,
            book INTEGER NOT NULL,
            format TEXT NOT NULL,
            uncompressed_size INTEGER,
            name TEXT,
            mtime TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, text TEXT
        );
        CREATE TABLE IF NOT EXISTS identifiers (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, type TEXT NOT NULL, val TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS languages (id INTEGER PRIMARY KEY, lang_code TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS books_languages_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS books_publishers_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY, rating INTEGER
        );
        CREATE TABLE IF NOT EXISTS books_ratings_link (
            id INTEGER PRIMARY KEY, book INTEGER NOT NULL, rating INTEGER NOT NULL
        );
    """)
    conn.commit()


# Singleton accessor
_db: CalibreDB | None = None


def get_calibre_db() -> CalibreDB:
    """Get a singleton CalibreDB instance."""
    global _db
    if _db is None:
        _db = CalibreDB()
    return _db
