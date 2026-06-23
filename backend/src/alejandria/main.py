"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from alejandria import __version__
from alejandria.config import get_settings
from alejandria.db import init_db
from alejandria.middleware.security_headers import (
    CSRFMiddleware,
    SecurityHeadersMiddleware,
)
from alejandria.routers import (
    auth,
    books,
    bulk,
    conversion,
    health,
    highlights,
    kindle,
    library,
    opds,
    reader,
    scraper,
    security,
    shelves,
    stats,
)
from alejandria.routers import (
    settings as settings_router,
)
from alejandria.services.scanner import LibraryScanner
from alejandria.services.scraper.manager import get_scraper_manager
from alejandria.utils.bootstrap import ensure_admin_user, ensure_library_dirs

logger = structlog.get_logger(__name__)


def _configure_logging(level: str, fmt: str) -> None:
    """Configure structured logging."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
    if fmt == "json":
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, level.upper(), logging.INFO)
            ),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB, ensure admin, start scanner."""
    settings = get_settings()
    _configure_logging(settings.log_level, settings.log_format)
    logger.info(
        "alejandria_starting",
        version=__version__,
        library_path=str(settings.library_path),
        calibre_enabled=settings.enable_calibre,
    )

    # Ensure required directories exist
    ensure_library_dirs()

    # Init database
    init_db()

    # Boot-time security warnings.
    if not settings.opds_require_auth:
        logger.warning(
            "opds_public_mode_active",
            message=(
                "OPDS is exposed without authentication (ALEJANDRIA_OPDS_REQUIRE_AUTH=false). "
                "Anyone who can reach this port can enumerate the library."
            ),
        )

    # Ensure default admin user
    await ensure_admin_user()

    # Start library scanner
    scanner = LibraryScanner()
    app.state.scanner = scanner
    scanner.start()

    # Start scraper manager
    scraper_manager = get_scraper_manager()
    app.state.scraper_manager = scraper_manager
    try:
        await scraper_manager.start()
    except Exception as e:
        logger.error("scraper_manager_start_failed", error=str(e))

    logger.info("alejandria_ready", url=f"http://{settings.host}:{settings.port}")
    yield

    # Shutdown
    logger.info("alejandria_stopping")
    try:
        await scraper_manager.stop()
    except Exception:
        pass
    scanner.stop()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Alejandría",
        version=__version__,
        description="Self-hosted ebook library",
        docs_url="/api/docs" if settings.dev_mode else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.dev_mode else None,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.base_url, "http://localhost:5173"] if settings.dev_mode else [settings.base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # API routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(library.router, prefix="/api/library", tags=["library"])
    app.include_router(books.router, prefix="/api/books", tags=["books"])
    app.include_router(bulk.router, prefix="/api/books/bulk", tags=["books-bulk"])
    app.include_router(reader.router, prefix="/api/reader", tags=["reader"])
    app.include_router(conversion.router, prefix="/api/convert", tags=["convert"])
    app.include_router(kindle.router, prefix="/api/kindle", tags=["kindle"])
    app.include_router(shelves.router, prefix="/api/shelves", tags=["shelves"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
    app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
    app.include_router(highlights.router, prefix="/api/highlights", tags=["highlights"])
    app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
    app.include_router(security.router, prefix="/api/security", tags=["security"])
    app.include_router(opds.router, prefix="/opds", tags=["opds"])

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )

    # Static frontend (SvelteKit build)
    static_path = Path(settings.static_path)
    if static_path.exists():
        # Mount _app, fonts, etc as static
        for subdir in ("_app", "fonts", "icons"):
            subdir_path = static_path / subdir
            if subdir_path.exists():
                app.mount(f"/{subdir}", StaticFiles(directory=subdir_path), name=subdir)

        # Serve static files individually
        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            fav = static_path / "favicon.ico"
            if fav.exists():
                return FileResponse(fav)
            return HTMLResponse(status_code=404)

        @app.get("/favicon.svg", include_in_schema=False)
        async def favicon_svg():
            fav = static_path / "favicon.svg"
            if fav.exists():
                return FileResponse(fav, media_type="image/svg+xml")
            return HTMLResponse(status_code=404)

        @app.get("/robots.txt", include_in_schema=False)
        async def robots():
            rob = static_path / "robots.txt"
            if rob.exists():
                return FileResponse(rob, media_type="text/plain")
            return HTMLResponse(status_code=404)

        @app.get("/theme-init.js", include_in_schema=False)
        async def theme_init():
            """Theme init script (externalized from app.html to satisfy strict CSP).

            Loaded in <head> before the SvelteKit bundle hydrates so the
            data-theme attribute is set synchronously and there's no FOUC.
            """
            ti = static_path / "theme-init.js"
            if ti.exists():
                return FileResponse(ti, media_type="application/javascript")
            return HTMLResponse(status_code=404)

        @app.get("/manifest.webmanifest", include_in_schema=False)
        async def manifest():
            mf = static_path / "manifest.webmanifest"
            if mf.exists():
                return FileResponse(mf, media_type="application/manifest+json")
            return HTMLResponse(status_code=404)

        @app.get("/sw.js", include_in_schema=False)
        async def service_worker():
            sw = static_path / "sw.js"
            if sw.exists():
                return FileResponse(sw, media_type="application/javascript")
            return HTMLResponse(status_code=404)

        # SPA fallback — serve index.html for any non-API route.
        # index.html must NEVER be cached: it references hashed asset filenames
        # (e.g. _app/immutable/nodes/4.AAAA.js) and a stale index points at
        # chunks the browser no longer requests. The hashed chunks themselves
        # are safe to cache forever.
        @app.get("/", include_in_schema=False)
        async def index_no_cache():
            index = static_path / "index.html"
            if index.exists():
                return FileResponse(
                    index,
                    media_type="text/html",
                    headers={"Cache-Control": "no-store, must-revalidate",
                             "Pragma": "no-cache"},
                )
            return HTMLResponse(
                "<h1>Alejandría backend is running</h1>"
                "<p>Frontend not built. Run <code>npm run build</code> in <code>frontend/</code>.</p>",
                status_code=200,
            )

        @app.get("/_app/version.json", include_in_schema=False)
        async def version_no_cache():
            v = static_path / "_app" / "version.json"
            if v.exists():
                return FileResponse(
                    v,
                    media_type="application/json",
                    headers={"Cache-Control": "no-store, must-revalidate",
                             "Pragma": "no-cache"},
                )
            return HTMLResponse(status_code=404)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # Don't shadow API routes (already mounted)
            if full_path.startswith(("api/", "opds/", "_app/", "fonts/", "icons/",
                                     "favicon.ico", "favicon.svg", "manifest.webmanifest", "robots.txt", "sw.js")):
                return HTMLResponse(status_code=404)
            index = static_path / "index.html"
            if index.exists():
                return FileResponse(
                    index,
                    media_type="text/html",
                    headers={"Cache-Control": "no-store, must-revalidate",
                             "Pragma": "no-cache"},
                )
            return HTMLResponse(
                "<h1>Alejandría backend is running</h1>"
                "<p>Frontend not built. Run <code>npm run build</code> in <code>frontend/</code>.</p>",
                status_code=200,
            )

    return app


app = create_app()
