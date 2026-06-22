"""Conversion router — on-the-fly format conversion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.convert import convert

router = APIRouter()


@router.post("/{book_id}/convert")
async def convert_book(
    book_id: int,
    target: str = Query(..., pattern=r"^(EPUB|PDF|MOBI|AZW3|TXT|HTML)$"),
    source: str | None = Query(None),
):
    """Convert a book to a different format (uses Calibre's ebook-convert)."""
    calibre = get_calibre_db()
    if not calibre.get_book(book_id):
        raise HTTPException(status_code=404, detail="Book not found")

    source_fmt = source
    if not source_fmt:
        first = calibre.get_first_format(book_id)
        if not first:
            raise HTTPException(status_code=400, detail="No source format")
        source_fmt = first[0]

    result = await convert(book_id, source_fmt, target, force=False)
    if not result:
        raise HTTPException(status_code=500, detail="Conversion failed")

    mime = {
        "EPUB": "application/epub+zip",
        "PDF": "application/pdf",
        "MOBI": "application/x-mobipocket-ebook",
        "AZW3": "application/vnd.amazon.ebook",
        "TXT": "text/plain",
        "HTML": "text/html",
    }.get(target.upper(), "application/octet-stream")

    return FileResponse(
        path=result,
        media_type=mime,
        filename=f"book_{book_id}.{target.lower()}",
    )
