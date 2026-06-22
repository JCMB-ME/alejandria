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
    for path in (settings.library_path, settings.config_path, settings.caches_path):
        path.mkdir(parents=True, exist_ok=True)
    # Covers cache subdirectory
    (settings.caches_path / "covers").mkdir(parents=True, exist_ok=True)
    (settings.caches_path / "conversions").mkdir(parents=True, exist_ok=True)
    logger.debug("ensured_library_dirs", library=settings.library_path)


async def ensure_admin_user() -> None:
    """Create the default admin user if no users exist."""
    settings = get_settings()
    with SessionLocal() as db:
        result = db.execute(select(User).limit(1)).scalar_one_or_none()
        if result is not None:
            return  # At least one user exists

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

        # Create default shelves for admin (icons are SVG filenames in /static/icons)
        for name, shelf_type, icon, color in [
            ("Currently Reading", ShelfType.READING, "reading", "#3B82F6"),
            ("Finished", ShelfType.FINISHED, "finished", "#10B981"),
            ("Wishlist", ShelfType.WISHLIST, "wishlist", "#F59E0B"),
            ("Favorites", ShelfType.FAVORITES, "favorite", "#EF4444"),
        ]:
            slug = name.lower().replace(" ", "-")
            shelf = Shelf(
                user_id=admin.id,
                name=name,
                slug=slug,
                shelf_type=shelf_type,
                icon=icon,
                color=color,
                is_public=False,
            )
            db.add(shelf)
        db.commit()
        logger.info("default_shelves_created")


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
