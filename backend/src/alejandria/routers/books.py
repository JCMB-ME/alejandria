"""Books router — list, search, get details."""

from __future__ import annotations

import asyncio
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user, get_optional_user  # noqa: F401
from alejandria.config import get_settings
from alejandria.db import get_db
from alejandria.models.annotation import Annotation
from alejandria.models.highlight import Highlight
from alejandria.models.progress import ReadingProgress
from alejandria.models.shelf import ShelfBook
from alejandria.models.user import User
from alejandria.schemas.book import BookDetail, BookListResponse
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.scanner import get_scanner
from alejandria.utils.log import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=BookListResponse)
async def list_books(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    search: str | None = None,
    author: int | None = None,
    tag: int | None = None,
    series: int | None = None,
    format: str | None = Query(None, pattern=r"^[A-Z0-9]{2,5}$"),
    language: str | None = Query(None, max_length=8),
    added_after: date | None = Query(None),
    added_before: date | None = Query(None),
    sort: str = Query(
        "sort_title",
        pattern=r"^(id|title|sort_title|timestamp|pubdate|last_modified|series_index|rating|last_read|progress)$",
    ),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
) -> BookListResponse | Response:
    """List books in the library with optional filters and pagination."""
    calibre = get_calibre_db()
    items, total = await calibre.alist_books(
        page=page, page_size=page_size, search=search,
        author_id=author, tag_id=tag, series_id=series,
        format=format, language=language,
        added_after=added_after.isoformat() if added_after else None,
        added_before=added_before.isoformat() if added_before else None,
        sort=sort, order=order,
        user_id=user.id,
    )
    etag_token = await calibre.aget_etag_token()
    etag = f'W/"{total}-{etag_token}"'
    if request.headers.get("if-none-match") == etag:
        # Returning a bare Response with status 304; the client will
        # treat it as not-modified and skip the body.
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return BookListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(get_optional_user)],
) -> BookDetail:
    """Get detailed metadata for a single book."""
    calibre = get_calibre_db()
    book = await calibre.aget_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return calibre._to_detail(book)


@router.get("/{book_id}/formats")
async def get_book_formats(book_id: int) -> dict:
    """List available formats for a book."""
    calibre = get_calibre_db()
    book = await calibre.aget_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return {
        "book_id": book_id,
        "formats": [
            {"fmt": f.fmt, "size": f.size, "mtime": f.mtime}
            for f in book.get("formats", [])
        ],
    }


@router.post("/upload", status_code=201)
async def upload_book(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Upload a new book and import it into the Calibre library."""
    settings = get_settings()

    # Check file extension
    ext = Path(file.filename).suffix.lower()
    allowed = {".epub", ".pdf", ".mobi", ".azw3", ".azw", ".fb2", ".djvu", ".rtf", ".docx", ".txt",
               ".html", ".htmlz", ".lit", ".lrf", ".odt", ".cbz", ".cbr"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}")

    # Save file to a temporary uploads directory
    temp_dir = settings.caches_path / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        scanner = get_scanner()
        res = await scanner.add_book(temp_path)
        if res.get("exit_code") != 0:
            logger.error("calibredb_add_failed", error=res.get("stderr") or res.get("error"))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to import book into library: {res.get('stderr') or res.get('error')}"
            )
    finally:
        # Always clean up the temporary upload file
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return {"status": "success", "message": "Book uploaded and imported successfully"}


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a book from the library and clean up associated database tables."""
    calibre = get_calibre_db()
    book = calibre.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    scanner = get_scanner()
    success = await scanner.remove_book(book_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete book from library")

    # Clean up associated database entries in backend DB
    db.query(ReadingProgress).filter(ReadingProgress.book_id == book_id).delete()
    db.query(ShelfBook).filter(ShelfBook.book_id == book_id).delete()
    db.query(Highlight).filter(Highlight.book_id == book_id).delete()
    db.query(Annotation).filter(Annotation.book_id == book_id).delete()
    db.commit()

    # Clean up cover cache
    settings = get_settings()
    cover_dir = settings.caches_path / "covers" / str(book_id)
    if cover_dir.exists():
        try:
            shutil.rmtree(cover_dir)
        except Exception:
            pass

    return None


@router.put("/{book_id}", response_model=BookDetail)
async def update_book(
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    title: str | None = Form(None),
    authors: str | None = Form(None),
    tags: str | None = Form(None),
    series: str | None = Form(None),
    series_index: float | None = Form(None),
    publisher: str | None = Form(None),
    languages: str | None = Form(None),
    comments: str | None = Form(None),
    rating: int | None = Form(None),
    cover_file: UploadFile | None = File(None),
) -> BookDetail:
    """Update metadata for a book in the library (using calibredb)."""
    calibre = get_calibre_db()
    book = calibre.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    settings = get_settings()
    fields = {}

    if title is not None:
        fields["title"] = title
    if authors is not None:
        # calibre set_metadata expects authors separated by &
        if "," in authors:
            fields["authors"] = " & ".join([a.strip() for a in authors.split(",") if a.strip()])
        else:
            fields["authors"] = authors
    if tags is not None:
        fields["tags"] = tags
    if series is not None:
        fields["series"] = series
    if series_index is not None:
        fields["series_index"] = str(series_index)
    if publisher is not None:
        fields["publisher"] = publisher
    if languages is not None:
        fields["languages"] = languages
    if comments is not None:
        fields["comments"] = comments
    if rating is not None:
        # rating is 0 to 5 in frontend, 0 to 10 in calibre db.
        fields["rating"] = str(min(10, max(0, rating * 2)))

    temp_path = None
    if cover_file is not None and cover_file.filename:
        # Save temp file
        temp_dir = settings.caches_path / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / cover_file.filename
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(cover_file.file, buffer)
            fields["cover"] = str(temp_path)
        except Exception as e:
            logger.error("save_cover_failed", error=str(e))
            if temp_path and temp_path.exists():
                try: os.remove(temp_path)
                except: pass
            raise HTTPException(status_code=500, detail="Failed to save cover image")

    try:
        if fields:
            scanner = get_scanner()
            res = await scanner.update_metadata(book_id, fields)
            if res.get("exit_code") != 0:
                logger.error("update_metadata_failed", error=res.get("stderr") or res.get("error"))
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update metadata: {res.get('stderr') or res.get('error')}"
                )

            # Invalidate cover cache if metadata or cover was modified
            cover_dir = settings.caches_path / "covers" / str(book_id)
            if cover_dir.exists():
                try:
                    shutil.rmtree(cover_dir)
                except Exception:
                    pass
    finally:
        # Always clean up temp cover file
        if temp_path and temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # Retrieve updated book details
    updated_book = calibre.get_book(book_id)
    if not updated_book:
        raise HTTPException(status_code=404, detail="Book not found after update")
    return calibre._to_detail(updated_book)
