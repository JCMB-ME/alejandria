"""Startup bootstrap utilities."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from alejandria.auth.security import hash_password
from alejandria.config import get_settings
from alejandria.db import SessionLocal
from alejandria.models.shelf import Shelf, ShelfType
from alejandria.models.user import User, UserRole
from alejandria.utils.log import get_logger

logger = get_logger(__name__)


def ensure_library_dirs() -> None:
    """Create required directories if they don't exist."""
    settings = get_settings()
    for path in (
        settings.library_path,
        settings.config_path,
        settings.caches_path,
        settings.scraper_output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    # Covers cache subdirectory
    (settings.caches_path / "covers").mkdir(parents=True, exist_ok=True)
    (settings.caches_path / "conversions").mkdir(parents=True, exist_ok=True)
    logger.debug("ensured_library_dirs", library=settings.library_path)


async def ensure_admin_user() -> None:
    """Create the default admin user from env vars if no users exist AND a
    password is configured.

    If no users exist and the admin password is empty, the SPA's /register
    page is responsible for creating the first user (always as ADMIN). This
    is the first-time-setup flow shown to fresh installs.
    """
    settings = get_settings()
    with SessionLocal() as db:
        result = db.execute(select(User).limit(1)).scalar_one_or_none()
        if result is not None:
            return  # At least one user exists

        if not settings.admin_password or settings.admin_password == "changeme":
            logger.info("first_time_setup_pending_register_via_ui")
            return

        logger.info("creating_default_admin", username=settings.admin_username)
        admin = User(
            username=settings.admin_username,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN,
            display_name="Administrator",
            is_active=True,
            can_download=True,
            can_edit_metadata=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        _create_default_shelves(db, admin.id)
        logger.info("default_shelves_created")


def _create_default_shelves(db, user_id: int) -> None:
    """Create the four default shelves for a user (icons are SVG filenames in /static/icons)."""
    for name, shelf_type, icon, color in [
        ("Currently Reading", ShelfType.READING, "reading", "#3B82F6"),
        ("Finished", ShelfType.FINISHED, "finished", "#10B981"),
        ("Wishlist", ShelfType.WISHLIST, "wishlist", "#F59E0B"),
        ("Favorites", ShelfType.FAVORITES, "favorite", "#EF4444"),
    ]:
        slug = name.lower().replace(" ", "-")
        shelf = Shelf(
            user_id=user_id,
            name=name,
            slug=slug,
            shelf_type=shelf_type,
            icon=icon,
            color=color,
            is_public=False,
        )
        db.add(shelf)
    db.commit()


def cleanup_orphaned_caches() -> int:
    """Remove cached files for books that no longer exist."""
    from alejandria.services.calibre_db import CalibreDB

    settings = get_settings()
    cache_root = settings.caches_path
    if not cache_root.exists():
        return 0

    calibre = CalibreDB()
    valid_ids = {str(b["id"]) for b in calibre.iter_books(fields=["id"])}

    removed = 0
    for sub in ("conversions", "covers"):
        d = cache_root / sub
        if not d.exists():
            continue
        for entry in d.iterdir():
            if entry.is_dir() and entry.name not in valid_ids:
                import shutil

                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
    return removed
