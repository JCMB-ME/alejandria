"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from alejandria import __version__
from alejandria.config import get_settings
from alejandria.db import SessionLocal
from alejandria.services.calibre_db import get_calibre_db

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Basic health check."""
    return {
        "status": "ok",
        "version": __version__,
        "service": "alejandria",
    }


@router.get("/health/ready")
async def readiness() -> dict:
    """Readiness check: verifies DB and library are accessible."""
    settings = get_settings()
    checks: dict[str, dict] = {}

    # App DB
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["app_db"] = {"status": "ok"}
    except Exception as e:
        checks["app_db"] = {"status": "error", "error": str(e)}

    # Calibre DB
    try:
        calibre = get_calibre_db()
        if calibre.exists:
            count = calibre.count_books()
            checks["calibre_db"] = {"status": "ok", "book_count": count}
        else:
            checks["calibre_db"] = {
                "status": "warning",
                "message": "No library found at " + str(calibre.db_path),
            }
    except Exception as e:
        checks["calibre_db"] = {"status": "error", "error": str(e)}

    # Calibre CLI
    if settings.enable_calibre:
        import shutil
        calibre_bin = shutil.which("ebook-convert") or "/opt/calibre/ebook-convert"
        import os
        if os.path.exists(calibre_bin):
            checks["calibre_cli"] = {"status": "ok", "path": calibre_bin}
        else:
            checks["calibre_cli"] = {
                "status": "error",
                "message": "Calibre CLI not found",
            }

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "version": __version__,
        "checks": checks,
    }
