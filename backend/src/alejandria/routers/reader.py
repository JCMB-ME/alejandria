"""Reader router — serve books to the in-browser reader."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.progress import ReadingProgress
from alejandria.models.user import User
from alejandria.schemas.progress import ProgressRead, ProgressUpdate
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.convert import get_readable_file

router = APIRouter()


@router.get("/{book_id}/file")
@router.get("/{book_id}/file/{filename}")
async def get_readable_book(
    book_id: int,
    user: Annotated[User, Depends(get_current_user)],
    fmt: str | None = Query(None, description="Preferred format (e.g. EPUB)"),
    filename: str | None = None,
):
    """Get the book file for reading.

    Requires authentication. Streams the file with range support
    (for large books). Converts to browser-native format if needed
    (MOBI -> EPUB, etc.).
    """
    calibre = get_calibre_db()
    if not calibre.get_book(book_id):
        raise HTTPException(status_code=404, detail="Book not found")

    result = await get_readable_file(book_id, preferred_fmt=fmt)
    if not result:
        raise HTTPException(status_code=500, detail="Could not produce readable file")

    mime, path = result
    return FileResponse(
        path=path,
        media_type=mime,
        filename=path.name,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{path.name}"',
        },
    )


@router.get("/{book_id}/download")
async def download_book(
    book_id: int,
    user: Annotated[User, Depends(get_current_user)],
    fmt: str | None = None,
):
    """Download the book in its original (or specified) format."""
    if not user.can_download:
        raise HTTPException(status_code=403, detail="Download not allowed")

    calibre = get_calibre_db()
    if fmt:
        path = calibre.get_format_path(book_id, fmt)
    else:
        result = calibre.get_first_format(book_id)
        if not result:
            raise HTTPException(status_code=404, detail="No formats available")
        fmt, path = result

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.get("/{book_id}/progress", response_model=ProgressRead | None)
async def get_progress(
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProgressRead | None:
    """Get reading progress for the current user + book."""
    p = db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user.id,
            ReadingProgress.book_id == book_id,
        )
    ).scalar_one_or_none()
    if not p:
        return None
    return ProgressRead.model_validate(p)


@router.put("/{book_id}/progress", response_model=ProgressRead)
async def update_progress(
    book_id: int,
    payload: ProgressUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProgressRead:
    """Update reading progress."""
    from datetime import datetime

    p = db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user.id,
            ReadingProgress.book_id == book_id,
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if not p:
        p = ReadingProgress(
            user_id=user.id,
            book_id=book_id,
            position=payload.position,
            position_type=payload.position_type,
            progress_pct=payload.progress_pct,
            started_at=now,
            device_type=payload.device_type,
            device_name=payload.device_name,
        )
        db.add(p)
    else:
        p.position = payload.position
        p.position_type = payload.position_type
        p.progress_pct = payload.progress_pct
        p.last_read_at = now
        p.device_type = payload.device_type or p.device_type
        p.device_name = payload.device_name or p.device_name
        if payload.reading_time_seconds:
            p.total_reading_time += payload.reading_time_seconds
        if payload.progress_pct >= 0.95 and not p.finished_at:
            p.finished_at = now

    db.commit()
    db.refresh(p)
    return ProgressRead.model_validate(p)


@router.delete("/{book_id}/progress")
async def delete_progress(
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Reset reading progress."""
    p = db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user.id,
            ReadingProgress.book_id == book_id,
        )
    ).scalar_one_or_none()
    if p:
        db.delete(p)
        db.commit()
    return {"status": "ok"}
