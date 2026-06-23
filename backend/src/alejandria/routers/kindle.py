"""Send-to-Kindle router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alejandria.auth.dependencies import get_current_user
from alejandria.config import get_settings
from alejandria.models.user import User
from alejandria.services.calibre_db import get_calibre_db
from alejandria.services.smtp import SMTPService

router = APIRouter()


class KindleSendRequest(BaseModel):
    """Send-to-Kindle request."""

    book_id: int
    to_email: str | None = None  # Defaults to user's kindle_email or first from env
    target_format: str = "EPUB"  # Kindle accepts EPUB, MOBI, AZW3, PDF


@router.post("/send")
async def send_to_kindle(
    payload: KindleSendRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Send a book to a Kindle email."""
    settings = get_settings()
    smtp = SMTPService()
    if not smtp.is_configured:
        raise HTTPException(
            status_code=503,
            detail="SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_FROM_EMAIL in .env",
        )

    to_email = (
        payload.to_email
        or user.kindle_email
        or (settings.parsed_kindle_emails[0] if settings.parsed_kindle_emails else None)
    )
    if not to_email:
        raise HTTPException(
            status_code=400,
            detail="No Kindle email specified. Set user.kindle_email or KINDLE_EMAILS env var.",
        )

    calibre = get_calibre_db()
    book = calibre.get_book(payload.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Get file in target format
    fmt_path = calibre.get_format_path(payload.book_id, payload.target_format)
    if not fmt_path or not fmt_path.exists():
        # Convert
        from alejandria.services.convert import convert

        fmt_path = await convert(payload.book_id, payload.target_format, force=False)
        if not fmt_path:
            raise HTTPException(
                status_code=500,
                detail=f"Could not produce {payload.target_format} format",
            )

    authors = book.get("authors", [])
    author_str = ", ".join(a.name for a in authors) if authors else "Unknown"
    title = book.get("title", "Untitled")

    success = await smtp.send_book(
        to_email, fmt_path, book_title=title, author=author_str
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {
        "status": "sent",
        "to": to_email,
        "book_id": payload.book_id,
        "title": title,
    }


@router.get("/status")
async def kindle_status(
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get Kindle/SMTP configuration status."""
    settings = get_settings()
    smtp = SMTPService()
    return {
        "smtp_configured": smtp.is_configured,
        "user_kindle_email": user.kindle_email,
        "default_kindle_emails": settings.parsed_kindle_emails,
    }
