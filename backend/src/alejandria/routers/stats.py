"""Stats router — reading statistics dashboard."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.user import User
from alejandria.services.stats import StatsService

router = APIRouter()
service = StatsService()


@router.get("")
@router.get("/")
async def root(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Alias for /overview — convenient default."""
    return service.user_overview(db, user.id)


@router.get("/overview")
async def overview(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return service.user_overview(db, user.id)


@router.get("/streak")
async def streak(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return service.reading_streak(db, user.id)


@router.get("/by-year")
async def by_year(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return service.reading_by_year(db, user.id)


@router.get("/daily")
async def daily(
    days: int = Query(30, ge=1, le=365),
    db: Annotated[Session, Depends(get_db)] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
) -> list[dict]:
    return service.daily_reading(db, user.id, days=days)
