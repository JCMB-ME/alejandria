"""Shelves router — user collections."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.progress import ReadingProgress
from alejandria.models.shelf import Shelf, ShelfBook, ShelfType
from alejandria.models.user import User
from alejandria.schemas.shelf import ShelfCreate, ShelfRead, ShelfUpdate, ShelfWithBooks
from alejandria.services.calibre_db import get_calibre_db
from alejandria.utils.paths import safe_filename

router = APIRouter()


@router.get("", response_model=list[ShelfRead])
async def list_shelves(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ShelfRead]:
    """List all shelves for the current user."""
    shelves = db.execute(
        select(Shelf).where(Shelf.user_id == user.id).order_by(Shelf.sort_order, Shelf.name)
    ).scalars().all()
    result: list[ShelfRead] = []
    for s in shelves:
        if s.shelf_type == ShelfType.READING:
            book_count = db.execute(
                select(ReadingProgress.book_id)
                .where(
                    ReadingProgress.user_id == user.id,
                    ReadingProgress.progress_pct > 0.0,
                    ReadingProgress.progress_pct < 0.95
                )
            ).all()
        elif s.shelf_type == ShelfType.FINISHED:
            book_count = db.execute(
                select(ReadingProgress.book_id)
                .where(
                    ReadingProgress.user_id == user.id,
                    ReadingProgress.progress_pct >= 0.95
                )
            ).all()
        else:
            book_count = db.execute(
                select(ShelfBook).where(ShelfBook.shelf_id == s.id)
            ).all()

        result.append(ShelfRead(
            id=s.id, user_id=s.user_id, name=s.name, slug=s.slug,
            description=s.description, icon=s.icon, color=s.color,
            is_public=s.is_public, shelf_type=s.shelf_type, sort_order=s.sort_order,
            book_count=len(book_count),
            created_at=s.created_at, updated_at=s.updated_at,
        ))
    return result


@router.post("", response_model=ShelfRead, status_code=201)
async def create_shelf(
    payload: ShelfCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ShelfRead:
    """Create a new shelf."""
    slug = payload.slug or safe_filename(payload.name).lower().replace(" ", "-")
    existing = db.execute(
        select(Shelf).where(Shelf.user_id == user.id, Shelf.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Shelf with that name/slug already exists")
    shelf = Shelf(
        user_id=user.id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        is_public=payload.is_public,
        shelf_type=payload.shelf_type,
    )
    db.add(shelf)
    db.commit()
    db.refresh(shelf)
    return ShelfRead(
        id=shelf.id, user_id=shelf.user_id, name=shelf.name, slug=shelf.slug,
        description=shelf.description, icon=shelf.icon, color=shelf.color,
        is_public=shelf.is_public, shelf_type=shelf.shelf_type, sort_order=shelf.sort_order,
        book_count=0, created_at=shelf.created_at, updated_at=shelf.updated_at,
    )


@router.get("/{shelf_id}", response_model=ShelfWithBooks)
async def get_shelf(
    shelf_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ShelfWithBooks:
    """Get a shelf with all its books."""
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")
    if shelf.shelf_type == ShelfType.READING:
        book_ids = list(db.execute(
            select(ReadingProgress.book_id)
            .where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.progress_pct > 0.0,
                ReadingProgress.progress_pct < 0.95
            )
            .order_by(ReadingProgress.last_read_at.desc())
        ).scalars())
    elif shelf.shelf_type == ShelfType.FINISHED:
        book_ids = list(db.execute(
            select(ReadingProgress.book_id)
            .where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.progress_pct >= 0.95
            )
            .order_by(ReadingProgress.finished_at.desc())
        ).scalars())
    else:
        book_ids = [r.book_id for r in db.execute(
            select(ShelfBook).where(ShelfBook.shelf_id == shelf_id).order_by(ShelfBook.sort_order)
        ).scalars()]
    calibre = get_calibre_db()
    books = []
    for bid in book_ids[:100]:
        book = calibre.get_book(bid)
        if book:
            books.append(calibre._to_summary(book))  # noqa: SLF001
    return ShelfWithBooks(
        id=shelf.id, user_id=shelf.user_id, name=shelf.name, slug=shelf.slug,
        description=shelf.description, icon=shelf.icon, color=shelf.color,
        is_public=shelf.is_public, shelf_type=shelf.shelf_type, sort_order=shelf.sort_order,
        book_count=len(book_ids), book_ids=book_ids, books=books,
        created_at=shelf.created_at, updated_at=shelf.updated_at,
    )


@router.patch("/{shelf_id}", response_model=ShelfRead)
async def update_shelf(
    shelf_id: int,
    payload: ShelfUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ShelfRead:
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shelf, field, value)
    db.commit()
    db.refresh(shelf)
    return ShelfRead.model_validate(shelf)


@router.delete("/{shelf_id}", status_code=204)
async def delete_shelf(
    shelf_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")
    if shelf.shelf_type != ShelfType.MANUAL:
        raise HTTPException(status_code=400, detail="Cannot delete auto shelf")
    db.delete(shelf)
    db.commit()


@router.post("/{shelf_id}/books/{book_id}", status_code=201)
async def add_book_to_shelf(
    shelf_id: int,
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")
    existing = db.execute(
        select(ShelfBook).where(ShelfBook.shelf_id == shelf_id, ShelfBook.book_id == book_id)
    ).scalar_one_or_none()
    if existing:
        return {"status": "already_present"}
    link = ShelfBook(shelf_id=shelf_id, book_id=book_id)
    db.add(link)
    db.commit()
    return {"status": "added"}


@router.delete("/{shelf_id}/books/{book_id}", status_code=204)
async def remove_book_from_shelf(
    shelf_id: int,
    book_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Shelf not found")
    link = db.execute(
        select(ShelfBook).where(ShelfBook.shelf_id == shelf_id, ShelfBook.book_id == book_id)
    ).scalar_one_or_none()
    if link:
        db.delete(link)
        db.commit()
