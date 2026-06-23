"""Library router — stats, authors, tags, series."""

from __future__ import annotations

import hashlib
from typing import Annotated

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from alejandria.auth.dependencies import get_current_user, get_optional_user
from alejandria.models.user import User
from alejandria.schemas.book import LibraryStats, SeriesInfo, TagInfo
from alejandria.schemas.filters import FilterOptions
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.scanner import get_scanner

router = APIRouter()


@router.get("/stats", response_model=LibraryStats)
async def library_stats(request: Request, response: Response) -> Response | LibraryStats:
    """Get overall library statistics."""
    scanner = get_scanner()
    calibre = get_calibre_db()
    stats = await calibre.aget_stats(last_scan=scanner.last_scan)
    etag_token = await calibre.aget_etag_token()
    etag = f'W/"{etag_token}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return stats


@router.get("/filters", response_model=FilterOptions)
async def library_filters(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> Response | FilterOptions:
    """Return the available filter values with counts, for the library page UI.

    ETag-based caching: if the books table's max timestamp is unchanged,
    subsequent calls return 304. Cache-Control: public, max-age=600.
    """
    calibre = get_calibre_db()
    etag_token = await calibre.aget_etag_token()
    etag = f'W/"{hashlib.md5(etag_token.encode()).hexdigest()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    authors, tags, series, formats, languages = await asyncio.gather(
        calibre.alist_authors_with_counts(),
        calibre.alist_tags_with_counts(),
        calibre.alist_series_with_counts(),
        calibre.alist_formats_with_counts(),
        calibre.alist_languages_with_counts(),
    )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return FilterOptions(
        authors=authors,
        tags=tags,
        series=series,
        formats=formats,
        languages=languages,
    )


@router.get("/authors")
async def list_authors() -> list[dict]:
    """List all authors in the library."""
    return [a.model_dump() for a in await get_calibre_db().alist_authors()]


@router.get("/authors/{author_id}")
async def get_author(author_id: int) -> dict:
    """Get author details + their books."""
    calibre = get_calibre_db()
    author = await calibre.aget_author(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    books, total = await calibre.alist_books(author_id=author_id, page_size=1000)
    return {
        **author.model_dump(),
        "book_count": total,
        "books": [b.model_dump() for b in books],
    }


@router.get("/tags", response_model=list[TagInfo])
async def list_tags() -> list[TagInfo]:
    """List all tags."""
    return await get_calibre_db().alist_tags()


@router.get("/tags/{tag_id}")
async def get_tag(tag_id: int) -> dict:
    """Get tag details + their books."""
    calibre = get_calibre_db()
    # Verify tag exists
    tags = await calibre.alist_tags()
    tag = next((t for t in tags if t.id == tag_id), None)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    books, total = await calibre.alist_books(tag_id=tag_id, page_size=1000)
    return {
        **tag.model_dump(),
        "book_count": total,
        "books": [b.model_dump() for b in books],
    }


@router.get("/series", response_model=list[SeriesInfo])
async def list_series() -> list[SeriesInfo]:
    """List all series."""
    return await get_calibre_db().alist_series()


@router.get("/series/{series_id}")
async def get_series(series_id: int) -> dict:
    """Get series details + books in order."""
    calibre = get_calibre_db()
    series = await calibre.aget_series(series_id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    # Page through books in series via the async list path.
    books, _ = await calibre.alist_books(series_id=series_id, page_size=1000, sort="series_index")
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
async def get_cover_endpoint(book_id: int, size: str = "medium"):
    """Get cover image (jpg)."""
    from fastapi.responses import Response

    from alejandria.services.cover import COVER_SIZES, get_cover

    if size not in COVER_SIZES:
        size = "medium"

    # get_cover is sync; the ebook-meta subprocess fallback can block for
    # up to 30s. Wrap in to_thread so the event loop stays free.
    data = await asyncio.to_thread(get_cover, book_id, size)
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