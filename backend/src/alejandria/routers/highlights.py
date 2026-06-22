"""Highlights and annotations router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
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
):
    h = service.update_highlight(db, user.id, highlight_id, payload)
    if not h:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return h


@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(
    highlight_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not service.delete_highlight(db, user.id, highlight_id):
        raise HTTPException(status_code=404, detail="Highlight not found")


@router.get("/export")
async def export_highlights(
    book_id: int | None = None,
    format: str = "markdown",
    db: Annotated[Session, Depends(get_db)] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
) -> Response:
    """Export highlights as Markdown / Notion / Obsidian compatible format."""
    if format != "markdown":
        raise HTTPException(status_code=400, detail="Only 'markdown' format supported currently")
    md = service.export_markdown(db, user.id, book_id=book_id)
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="highlights.md"'},
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
