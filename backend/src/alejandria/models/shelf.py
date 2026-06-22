"""Shelf and ShelfBook models (user collections)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alejandria.db import Base


class ShelfType(str, PyEnum):
    """Type of shelf — controls auto-population."""

    MANUAL = "manual"        # user adds books
    READING = "reading"      # currently reading (auto)
    FINISHED = "finished"    # finished (auto)
    WISHLIST = "wishlist"    # want to read
    FAVORITES = "favorites"  # starred
    CUSTOM = "custom"


class Shelf(Base):
    """A user shelf (collection of books)."""

    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    shelf_type: Mapped[ShelfType] = mapped_column(
        Enum(ShelfType), default=ShelfType.MANUAL, nullable=False
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    books: Mapped[list[ShelfBook]] = relationship(
        "ShelfBook", back_populates="shelf", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_user_shelf_slug"),)

    def __repr__(self) -> str:
        return f"<Shelf {self.name!r} user={self.user_id}>"


class ShelfBook(Base):
    """Junction table linking shelves to books."""

    __tablename__ = "shelf_books"
    __table_args__ = (UniqueConstraint("shelf_id", "book_id", name="uq_shelf_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shelf_id: Mapped[int] = mapped_column(
        ForeignKey("shelves.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    shelf: Mapped[Shelf] = relationship("Shelf", back_populates="books")
