"""Highlights and annotations router."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.highlight import Highlight
from alejandria.models.user import User
from alejandria.schemas.highlight import (
    AnnotationCreate,
    AnnotationRead,
    AnnotationUpdate,
    HighlightCreate,
    HighlightRead,
    HighlightUpdate,
)
from alejandria.services.highlights import HighlightService

router = APIRouter()
service = HighlightService()


# Highlights ----------------------------------------------------------------

@router.get("", response_model=list[HighlightRead])
async def list_highlights(
    book_id: int | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
) -> list[Highlight]:
    return service.list_highlights(db, user.id, book_id=book_id)


@router.post("", response_model=HighlightRead, status_code=201)
async def create_highlight(
    payload: HighlightCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Highlight:
    return service.create_highlight(db, user.id, payload)


@router.patch("/{highlight_id}", response_model=HighlightRead)
async def update_highlight(
    highlight_id: int,
    payload: HighlightUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Highlight:
    """PATCH a highlight.

    Returns 403 when the highlight exists but belongs to another user
    (audit's H4 finding — was previously indistinguishable from 404).
    Returns 404 when the highlight doesn't exist. Returns 422 when
    `color` is not a #RRGGBB hex string (handled by Pydantic).
    """
    try:
        return service.update_highlight(db, user, highlight_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Highlight not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your highlight")


@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(
    highlight_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        service.delete_highlight(db, user, highlight_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Highlight not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your highlight")


@router.get("/export")
async def export_highlights(
    book_id: int | None = None,
    format: str = "markdown",
    db: Annotated[Session, Depends(get_db)] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
) -> Response:
    """Export highlights as Markdown.

    - `book_id` present → single markdown file with the book title as H1.
    - `book_id` absent → zip with one `.md` per book the user has highlights in.

    Only markdown is supported for now. Other formats return 400.
    """
    if format != "markdown":
        raise HTTPException(
            status_code=400,
            detail="Only 'markdown' format supported currently",
        )

    if book_id is not None:
        try:
            md = service.export_markdown(db, user.id, book_id=book_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Book not found")
        return Response(
            content=md,
            media_type="text/markdown",
            headers={
                "Content-Disposition": 'attachment; filename="highlights.md"'
            },
        )

    blob = service.export_markdown_zip(db, user.id)
    today = date.today().isoformat()
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="highlights-{today}.zip"'
            )
        },
    )


# Annotations ---------------------------------------------------------------

@router.post("/annotations", response_model=AnnotationRead, status_code=201)
async def create_annotation(
    payload: AnnotationCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return service.create_annotation(db, user.id, payload)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationRead)
async def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    a = service.update_annotation(db, user.id, annotation_id, payload)
    if not a:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return a


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not service.delete_annotation(db, user.id, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")
