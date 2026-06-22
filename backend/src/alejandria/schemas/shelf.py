"""Shelf schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from alejandria.models.shelf import ShelfType
from alejandria.schemas.book import BookSummary


class ShelfBase(BaseModel):
    """Common shelf fields."""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    is_public: bool = False
    shelf_type: ShelfType = ShelfType.MANUAL


class ShelfCreate(ShelfBase):
    """Create shelf payload."""

    slug: str | None = Field(default=None, max_length=128, pattern=r"^[a-z0-9-]+$")


class ShelfUpdate(BaseModel):
    """Update shelf payload."""

    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    is_public: bool | None = None
    sort_order: int | None = None


class ShelfRead(ShelfBase):
    """Shelf as returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    slug: str
    sort_order: int
    book_count: int = 0
    created_at: datetime
    updated_at: datetime


class ShelfWithBooks(ShelfRead):
    """Shelf with included book IDs and summaries."""

    book_ids: list[int] = []
    books: list[BookSummary] = []
