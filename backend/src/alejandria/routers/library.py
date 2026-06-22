"""Library router — stats, authors, tags, series."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_optional_user
from alejandria.db import get_db
from alejandria.models.user import User
from alejandria.schemas.book import BookSummary, LibraryStats, SeriesInfo, TagInfo
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.scanner import get_scanner

router = APIRouter()


@router.get("/stats", response_model=LibraryStats)
async def library_stats() -> LibraryStats:
    """Get overall library statistics."""
    scanner = get_scanner()
    return get_calibre_db().get_stats(last_scan=scanner.last_scan)


@router.get("/authors")
async def list_authors() -> list[dict]:
    """List all authors in the library."""
    return [a.model_dump() for a in get_calibre_db().list_authors()]


@router.get("/authors/{author_id}")
async def get_author(author_id: int) -> dict:
    """Get author details + their books."""
    calibre = get_calibre_db()
    author = calibre.get_author(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    books, total = calibre.list_books(author_id=author_id, page_size=1000)
    return {
        **author.model_dump(),
        "book_count": total,
        "books": [b.model_dump() for b in books],
    }


@router.get("/tags", response_model=list[TagInfo])
async def list_tags() -> list[TagInfo]:
    """List all tags."""
    return get_calibre_db().list_tags()


@router.get("/tags/{tag_id}")
async def get_tag(tag_id: int) -> dict:
    """Get tag details + their books."""
    calibre = get_calibre_db()
    # Verify tag exists
    tag = next((t for t in calibre.list_tags() if t.id == tag_id), None)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    books, total = calibre.list_books(tag_id=tag_id, page_size=1000)
    return {
        **tag.model_dump(),
        "book_count": total,
        "books": [b.model_dump() for b in books],
    }


@router.get("/series", response_model=list[SeriesInfo])
async def list_series() -> list[SeriesInfo]:
    """List all series."""
    return get_calibre_db().list_series()


@router.get("/series/{series_id}")
async def get_series(series_id: int) -> dict:
    """Get series details + books in order."""
    calibre = get_calibre_db()
    series = calibre.get_series(series_id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    books = calibre.get_books_in_series(series_id)
    return {
        **series.model_dump(),
        "books": [b.model_dump() for b in books],
    }


@router.post("/rescan")
async def trigger_rescan(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> dict:
    """Trigger a full library rescan. Admin only."""
    if user is None or user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    scanner = get_scanner()
    task = scanner.trigger_rescan()
    return {"status": "started", "scanning": scanner.is_scanning}


@router.get("/rescan/status")
async def rescan_status() -> dict:
    """Get current rescan status."""
    scanner = get_scanner()
    return {
        "is_scanning": scanner.is_scanning,
        "last_scan": scanner.last_scan,
    }


@router.get("/covers/{book_id}.jpg")
async def get_cover(book_id: int, size: str = "medium"):
    """Get cover image (jpg)."""
    from fastapi.responses import Response

    from alejandria.services.cover import COVER_SIZES, get_cover

    if size not in COVER_SIZES:
        size = "medium"

    data = get_cover(book_id, size)
    if not data:
        # Return placeholder
        return Response(
            content=_placeholder_svg(book_id),
            media_type="image/svg+xml",
            status_code=200,
        )
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _placeholder_svg(book_id: int) -> bytes:
    """Generate a placeholder cover SVG."""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300">
  <rect width="200" height="300" fill="#1A1816"/>
  <text x="100" y="150" font-family="serif" font-size="14" fill="#E8E4DC" text-anchor="middle">Book {book_id}</text>
</svg>'''
    return svg.encode("utf-8")
