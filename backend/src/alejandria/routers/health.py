"""Health check endpoints."""

from __future__ import annotations

import os
import shutil

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from alejandria import __version__
from alejandria.config import get_settings
from alejandria.db import SessionLocal
from alejandria.services.calibre_db import get_calibre_db

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness probe: returns 200 if the process is alive.

    Use this for orchestrators that need to distinguish a dead process
    from a degraded one (k8s `livenessProbe`, Docker `HEALTHCHECK`).
    """
    return {
        "status": "ok",
        "version": __version__,
        "service": "alejandria",
    }


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """Readiness probe: verifies DB, Calibre, and scanner are functional.

    Returns 503 if any check fails so Docker / k8s can take the container
    out of rotation. Use this for orchestrators that route traffic
    (k8s `readinessProbe`, Docker Compose `healthcheck.test`).
    """
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

    # Scanner (best-effort — the scanner is not started in some test fixtures)
    try:
        from alejandria.services.scanner import get_scanner
        scanner = get_scanner()
        checks["scanner"] = {
            "status": "ok" if scanner._observer is not None else "not_running",
            "last_scan": scanner.last_scan.isoformat() if scanner.last_scan else None,
        }
    except Exception as e:
        checks["scanner"] = {"status": "error", "error": str(e)}

    # Calibre CLI
    if settings.enable_calibre:
        calibre_bin = shutil.which("ebook-convert") or "/opt/calibre/ebook-convert"
        if os.path.exists(calibre_bin):
            checks["calibre_cli"] = {"status": "ok", "path": calibre_bin}
        else:
            checks["calibre_cli"] = {"status": "error", "message": "Calibre CLI not found"}

    # 503 if any check is in error status. Warnings (no library yet) are OK.
    has_error = any(c.get("status") == "error" for c in checks.values())
    if has_error:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "degraded",
            "version": __version__,
            "checks": checks,
        }

    return {
        "status": "ok",
        "version": __version__,
        "checks": checks,
    }
