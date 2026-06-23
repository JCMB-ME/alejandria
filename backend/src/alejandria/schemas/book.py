"""Book-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookAuthor(BaseModel):
    """Author summary."""

    id: int
    name: str
    sort: str | None = None


class TagInfo(BaseModel):
    """Tag summary."""

    id: int
    name: str


class SeriesInfo(BaseModel):
    """Series summary."""

    id: int
    name: str
    sort: str | None = None


class BookFormat(BaseModel):
    """Available format for a book."""

    fmt: str  # EPUB, PDF, MOBI, etc.
    path: str
    size: int
    mtime: datetime | None = None


class BookSummary(BaseModel):
    """Book as listed in browse/search results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    sort_title: str | None = None
    authors: list[BookAuthor] = []
    tags: list[TagInfo] = []
    series: SeriesInfo | None = None
    series_index: float | None = None
    languages: list[str] = []
    pubdate: datetime | None = None
    publisher: str | None = None
    rating: int | None = None
    cover_path: str | None = None
    has_cover: bool = False
    formats: list[BookFormat] = []


class BookDetail(BookSummary):
    """Book detail with full metadata."""

    description: str | None = None
    comments: str | None = None
    identifiers: dict[str, str] = {}
    timestamp: datetime | None = None
    last_modified: datetime | None = None
    # Per-user fields (optional, populated when authenticated)
    user_progress: float | None = None
    user_finished: bool | None = None
    on_shelves: list[int] = []


class BookListResponse(BaseModel):
    """Paginated book list."""

    items: list[BookSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class LibraryStats(BaseModel):
    """Library statistics."""

    total_books: int
    total_authors: int
    total_tags: int
    total_series: int
    total_size_bytes: int
    formats: dict[str, int]  # EPUB: 123, PDF: 45, ...
    last_scan: datetime | None = None
