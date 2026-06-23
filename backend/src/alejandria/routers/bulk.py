"""Bulk operations router — multi-select actions on books.

All endpoints are auth-required and capped at 500 books per request.
Pydantic max_length=500 enforces the cap at parse time; the helpers below
raise 413/400 for clarity.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.shelf import Shelf, ShelfBook
from alejandria.models.user import User
from alejandria.schemas.filters import (
    BulkDeleteRequest,
    BulkResult,
    BulkShelfRequest,
    BulkTagsRequest,
)
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.scanner import get_scanner

router = APIRouter()


def _ensure_cap(book_ids: list[int]) -> None:
    if len(book_ids) > 500:
        raise HTTPException(
            status_code=413,
            detail=f"Bulk operation cap is 500 books; got {len(book_ids)}.",
        )
    if not book_ids:
        raise HTTPException(status_code=400, detail="book_ids is empty.")


@router.post("/add-to-shelf", response_model=BulkResult)
async def bulk_add_to_shelf(
    payload: BulkShelfRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """Add multiple books to a shelf. Idempotent — existing rows are skipped."""
    _ensure_cap(payload.book_ids)
    shelf = db.get(Shelf, payload.shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")

    calibre = get_calibre_db()
    affected = 0
    skipped = 0
    failed = 0
    for book_id in payload.book_ids:
        book = calibre.get_book(book_id)
        if not book:
            failed += 1
            continue
        existing = db.execute(
            select(ShelfBook).where(
                ShelfBook.shelf_id == payload.shelf_id,
                ShelfBook.book_id == book_id,
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        db.add(ShelfBook(shelf_id=payload.shelf_id, book_id=book_id))
        affected += 1
    db.commit()
    return BulkResult(affected=affected, failed=failed, skipped=skipped)


@router.post("/remove-from-shelf", response_model=BulkResult)
async def bulk_remove_from_shelf(
    payload: BulkShelfRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """Remove multiple books from a shelf. Idempotent — missing rows are skipped."""
    _ensure_cap(payload.book_ids)
    shelf = db.get(Shelf, payload.shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")

    affected = 0
    for book_id in payload.book_ids:
        link = db.execute(
            select(ShelfBook).where(
                ShelfBook.shelf_id == payload.shelf_id,
                ShelfBook.book_id == book_id,
            )
        ).scalar_one_or_none()
        if link:
            db.delete(link)
            affected += 1
    db.commit()
    return BulkResult(affected=affected)


@router.post("/delete", response_model=BulkResult)
async def bulk_delete(
    payload: BulkDeleteRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """Delete multiple books from the library."""
    _ensure_cap(payload.book_ids)
    calibre = get_calibre_db()
    scanner = get_scanner()
    affected = 0
    failed = 0
    for book_id in payload.book_ids:
        book = calibre.get_book(book_id)
        if not book:
            failed += 1
            continue
        success = await scanner.remove_book(book_id)
        if not success:
            failed += 1
            continue
        # Clean up app DB tables for this book
        from alejandria.models.annotation import Annotation
        from alejandria.models.highlight import Highlight
        from alejandria.models.progress import ReadingProgress

        db.query(ReadingProgress).filter(ReadingProgress.book_id == book_id).delete()
        db.query(ShelfBook).filter(ShelfBook.book_id == book_id).delete()
        db.query(Highlight).filter(Highlight.book_id == book_id).delete()
        db.query(Annotation).filter(Annotation.book_id == book_id).delete()
        db.commit()
        affected += 1
    return BulkResult(affected=affected, failed=failed)


@router.post("/set-tags", response_model=BulkResult)
async def bulk_set_tags(
    payload: BulkTagsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """REPLACE tags on multiple books (Calibre-level)."""
    _ensure_cap(payload.book_ids)
    calibre = get_calibre_db()
    scanner = get_scanner()
    affected = 0
    failed = 0
    target_tags = ",".join(payload.tags)
    for book_id in payload.book_ids:
        book = calibre.get_book(book_id)
        if not book:
            failed += 1
            continue
        res = await scanner.update_metadata(book_id, {"tags": target_tags})
        if res.get("exit_code") != 0:
            failed += 1
            continue
        affected += 1
    return BulkResult(affected=affected, failed=failed)


@router.post("/add-tags", response_model=BulkResult)
async def bulk_add_tags(
    payload: BulkTagsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """ADD to existing tags on multiple books (union)."""
    _ensure_cap(payload.book_ids)
    calibre = get_calibre_db()
    scanner = get_scanner()
    affected = 0
    failed = 0
    for book_id in payload.book_ids:
        book = calibre.get_book(book_id)
        if not book:
            failed += 1
            continue
        existing = {t.name for t in (book.get("tags") or [])}
        union_tags = sorted(existing | set(payload.tags))
        res = await scanner.update_metadata(
            book_id, {"tags": ",".join(union_tags)},
        )
        if res.get("exit_code") != 0:
            failed += 1
            continue
        affected += 1
    return BulkResult(affected=affected, failed=failed)


@router.post("/remove-tags", response_model=BulkResult)
async def bulk_remove_tags(
    payload: BulkTagsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BulkResult:
    """REMOVE tags from multiple books (difference)."""
    _ensure_cap(payload.book_ids)
    calibre = get_calibre_db()
    scanner = get_scanner()
    affected = 0
    failed = 0
    for book_id in payload.book_ids:
        book = calibre.get_book(book_id)
        if not book:
            failed += 1
            continue
        existing = {t.name for t in (book.get("tags") or [])}
        remaining = sorted(existing - set(payload.tags))
        res = await scanner.update_metadata(
            book_id, {"tags": ",".join(remaining)},
        )
        if res.get("exit_code") != 0:
            failed += 1
            continue
        affected += 1
    return BulkResult(affected=affected, failed=failed)
