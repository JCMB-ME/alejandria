"""ScraperManager — DB-backed queue + persistent worker for the scraper.

Lifecycle:
  start() — recover crashed jobs, load YAML adapters, lazily start Playwright
            browser, spawn the persistent "pump" task.
  stop()  — cancel in-flight tasks and close the browser.
  submit() — validate URL + rate-limit + INSERT a queued ScrapeJob row.
  cancel() — mark a job as 'cancelled' (the worker checks this flag).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.config import get_settings
from alejandria.db import SessionLocal
from alejandria.models.scrape_job import ScrapeJob, ScrapeJobStatus
from alejandria.schemas.scraper import ScrapeJobCreate
from alejandria.services.scraper.adapters.base import PageSnapshot
from alejandria.services.scraper.adapters.generic import GenericAdapter
from alejandria.services.scraper.adapters.loader import (
    YamlAdapter,
    compile_yaml_adapters,
    load_yaml_adapters,
)
from alejandria.services.scraper.image_fetch import FetchedImage, fetch_image
from alejandria.services.scraper.packagers.cbz import build_cbz
from alejandria.services.scraper.packagers.epub import build_epub
from alejandria.services.scraper.packagers.pdf import build_pdf
from alejandria.services.scraper.rate_limit import JobRateLimiter
from alejandria.services.scraper.ssrf import validate_url
from alejandria.utils.log import get_logger

logger = get_logger(__name__)

# How often the pump task scans for queued jobs.
_PUMP_INTERVAL_S = 5.0
# Per-job worker health-check
_WORKER_CANCEL_CHECK_EVERY_PAGES = 1


def _re_find_calibre_id(stdout: str) -> int | None:
    """Parse `calibredb add` stdout for the assigned book id."""
    m = re.search(r"\badded book id(?:=|:)\s*(\d+)", stdout)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # Alternative: calibredb may print "Added book id: 12" or similar.
    m = re.search(r"\bbook\s*id[:\s=]+(\d+)", stdout, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


class ScraperManager:
    """Top-level orchestrator for the scraper subsystem."""

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._browser: Any = None
        self._playwright_ctx: Any = None
        self._semaphore: asyncio.Semaphore | None = None
        self._stopped = asyncio.Event()
        self._pump_task: asyncio.Task | None = None
        self._yaml_adapters: list[YamlAdapter] = []
        self._runtime_adapters: list = []
        self._generic: GenericAdapter = GenericAdapter()
        self._http_session: Any = None

    # --- public API ----------------------------------------------------

    async def start(self) -> None:
        """Start the manager: recover jobs, load adapters, launch browser + pump."""
        settings = get_settings()
        if not settings.scraper_enabled:
            logger.info("scraper_disabled_by_config")
            return

        # Mark orphaned in-flight jobs as failed.
        self._recover_orphaned_jobs()

        # Load YAML adapters (no-op if the file is missing).
        try:
            self._yaml_adapters = load_yaml_adapters(settings.scraper_adapters_file)
            self._runtime_adapters = compile_yaml_adapters(self._yaml_adapters)
            logger.info(
                "scraper_yaml_adapters_loaded",
                count=len(self._runtime_adapters),
                path=str(settings.scraper_adapters_file),
            )
        except Exception as e:  # noqa: BLE001
            logger.error("scraper_yaml_adapters_load_failed", error=str(e))
            self._yaml_adapters = []
            self._runtime_adapters = []

        # Concurrency semaphore
        self._semaphore = asyncio.Semaphore(settings.scraper_max_concurrent_jobs)

        # Start persistent pump
        self._stopped.clear()
        self._pump_task = asyncio.create_task(self._pump_loop())
        logger.info("scraper_manager_started")

    async def stop(self) -> None:
        """Stop the manager, cancel in-flight tasks, close the browser."""
        self._stopped.set()
        for t in list(self._tasks.values()):
            t.cancel()
        for t in list(self._tasks.values()):
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks.clear()
        if self._pump_task:
            self._pump_task.cancel()
            try:
                await self._pump_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._pump_task = None
        if self._http_session is not None:
            try:
                await self._http_session.close()
            except Exception:  # noqa: BLE001
                pass
            self._http_session = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
        if self._playwright_ctx is not None:
            try:
                await self._playwright_ctx.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._playwright_ctx = None
        logger.info("scraper_manager_stopped")

    async def submit(
        self, db: Session, user_id: int, payload: ScrapeJobCreate
    ) -> ScrapeJob:
        """Validate + persist a new scrape job."""
        settings = get_settings()
        if not settings.scraper_enabled:
            raise RuntimeError("Scraper is disabled in configuration")

        canonical_url = validate_url(payload.url)
        JobRateLimiter().check(db, user_id)

        job = ScrapeJob(
            user_id=user_id,
            url=canonical_url,
            title=payload.title,
            adapter_name=payload.adapter_name or "generic",
            formats_json=json.dumps(payload.formats),
            destinations_json=json.dumps(payload.destinations),
            status=ScrapeJobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    async def cancel(self, db: Session, job_id: int, user_id: int) -> ScrapeJob:
        """Mark a job as cancelled (no-op if it is already terminal)."""
        job = db.get(ScrapeJob, job_id)
        if not job or job.user_id != user_id:
            raise LookupError("ScrapeJob not found")
        if job.status in (ScrapeJobStatus.DONE, ScrapeJobStatus.FAILED, ScrapeJobStatus.CANCELLED):
            return job
        job.status = ScrapeJobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    async def list_jobs(self, db: Session, user_id: int) -> list[ScrapeJob]:
        stmt = (
            select(ScrapeJob)
            .where(ScrapeJob.user_id == user_id)
            .order_by(ScrapeJob.created_at.desc())
        )
        return list(db.execute(stmt).scalars())

    async def get_job(self, db: Session, job_id: int, user_id: int) -> ScrapeJob | None:
        job = db.get(ScrapeJob, job_id)
        if not job or job.user_id != user_id:
            return None
        return job

    # --- private helpers ----------------------------------------------

    def _recover_orphaned_jobs(self) -> None:
        """On startup, mark scraping/packaging jobs as failed (server restarted)."""
        with SessionLocal() as db:
            stmt = select(ScrapeJob).where(
                ScrapeJob.status.in_(
                    [ScrapeJobStatus.SCRAPING, ScrapeJobStatus.PACKAGING]
                )
            )
            rows = list(db.execute(stmt).scalars())
            for r in rows:
                r.status = ScrapeJobStatus.FAILED
                r.error = "Server restarted while job was running"
                r.completed_at = datetime.now(timezone.utc)
            if rows:
                db.commit()
                logger.info("scraper_recovered_orphaned_jobs", count=len(rows))

    def _pick_adapter(self, url: str) -> Any:
        """Return the first YAML adapter whose regex matches, else the generic one."""
        for adapter in self._runtime_adapters:
            if adapter.matches(url):
                return adapter
        return self._generic

    async def _ensure_browser(self) -> None:
        """Lazily start Playwright + Chromium and an aiohttp session."""
        if self._browser is not None and self._http_session is not None:
            return
        settings = get_settings()
        try:
            from playwright.async_api import async_playwright

            self._playwright_ctx = await async_playwright().start()
            launch_kwargs: dict[str, Any] = {"headless": settings.scraper_browser_headless}
            if settings.scraper_proxy:
                launch_kwargs["proxy"] = {"server": settings.scraper_proxy}
            self._browser = await self._playwright_ctx.chromium.launch(**launch_kwargs)
        except Exception as e:  # noqa: BLE001
            logger.error("scraper_browser_start_failed", error=str(e))
            self._browser = None
            return
        import aiohttp  # local import — aiohttp is in transitive deps

        self._http_session = aiohttp.ClientSession(
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=aiohttp.ClientTimeout(total=60),
        )

    async def _pump_loop(self) -> None:
        """Persistent loop: every _PUMP_INTERVAL_S, look for queued jobs and
        dispatch them under the semaphore."""
        while not self._stopped.is_set():
            try:
                with SessionLocal() as db:
                    queued = list(
                        db.execute(
                            select(ScrapeJob)
                            .where(ScrapeJob.status == ScrapeJobStatus.QUEUED)
                            .order_by(ScrapeJob.created_at.asc())
                        ).scalars()
                    )
                    for job in queued:
                        if job.id in self._tasks:
                            continue
                        task = asyncio.create_task(self._run_job(job.id))
                        self._tasks[job.id] = task
            except Exception as e:  # noqa: BLE001
                logger.error("scraper_pump_iteration_failed", error=str(e))
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=_PUMP_INTERVAL_S)
            except asyncio.TimeoutError:
                continue
            else:
                return

    async def _run_job(self, job_id: int) -> None:
        """Run a single job end-to-end (scraping -> packaging -> done)."""
        settings = get_settings()
        assert self._semaphore is not None
        async with self._semaphore:
            try:
                await self._ensure_browser()
                if self._browser is None:
                    with SessionLocal() as db:
                        job = db.get(ScrapeJob, job_id)
                        if not job:
                            return
                        job.status = ScrapeJobStatus.FAILED
                        job.error = "Browser could not start (check Playwright install)"
                        job.completed_at = datetime.now(timezone.utc)
                        db.commit()
                    return

                # Load job from DB
                with SessionLocal() as db:
                    job = db.get(ScrapeJob, job_id)
                    if not job:
                        return
                    if job.status == ScrapeJobStatus.CANCELLED:
                        return
                    job.status = ScrapeJobStatus.SCRAPING
                    job.started_at = datetime.now(timezone.utc)
                    job.error = None
                    job.progress_pct = 0.0
                    db.commit()
                    url = job.url
                    title = job.title or "Scraped Book"
                    formats = json.loads(job.formats_json or "[]")
                    destinations = json.loads(job.destinations_json or "[]")
                    adapter_name = job.adapter_name
                    job_dir = settings.scraper_output_dir / str(job_id)
                    pages_dir = job_dir / "pages"
                    pages_dir.mkdir(parents=True, exist_ok=True)

                adapter = self._pick_adapter(url)
                if adapter_name and adapter_name != "generic" and adapter_name != adapter.name:
                    # Honor explicit adapter_name if it matches a YAML one
                    for a in self._runtime_adapters:
                        if a.name == f"yaml:{adapter_name}":
                            adapter = a
                            break

                images: list[FetchedImage] = []
                page_index = 1
                current_url: str | None = url
                next_url: str | None = url
                total_bytes = 0
                max_bytes = settings.scraper_max_total_size_mb * 1024 * 1024
                max_pages = settings.scraper_max_pages_per_job

                while next_url and page_index <= max_pages:
                    # Cancel check
                    with SessionLocal() as db:
                        job = db.get(ScrapeJob, job_id)
                        if not job:
                            return
                        if job.status == ScrapeJobStatus.CANCELLED:
                            return
                        current_status = job.status
                    if current_status == ScrapeJobStatus.CANCELLED:
                        return

                    current_url = next_url
                    snapshot: PageSnapshot = await adapter.fetch_page(self._browser, current_url)
                    if not snapshot.image_urls:
                        # No images — either a bad page or end of book.
                        break

                    # Re-open a page for the next_url computation. We need a
                    # fresh Page because the adapter may have closed it.
                    page = await self._browser.new_page()
                    try:
                        await page.goto(current_url, wait_until="domcontentloaded", timeout=30_000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10_000)
                        except Exception:  # noqa: BLE001
                            pass

                        for img_url in snapshot.image_urls:
                            if page_index > max_pages:
                                break
                            if total_bytes >= max_bytes:
                                with SessionLocal() as db:
                                    job = db.get(ScrapeJob, job_id)
                                    if job:
                                        job.status = ScrapeJobStatus.FAILED
                                        job.error = "Job exceeded max total size"
                                        job.completed_at = datetime.now(timezone.utc)
                                        db.commit()
                                return
                            try:
                                fetched = await fetch_image(
                                    self._http_session, img_url
                                )
                            except ValueError as e:
                                logger.warning(
                                    "scraper_image_skipped", url=img_url, error=str(e)
                                )
                                continue
                            except Exception as e:  # noqa: BLE001
                                logger.warning(
                                    "scraper_image_error", url=img_url, error=str(e)
                                )
                                continue

                            page_filename = pages_dir / f"page-{page_index:04d}.{fetched.filename_hint.rsplit('.', 1)[-1] or 'jpg'}"
                            page_filename.write_bytes(fetched.bytes)
                            fetched.filename_hint = page_filename.name
                            images.append(fetched)
                            total_bytes += len(fetched.bytes)
                            page_index += 1

                            with SessionLocal() as db:
                                job = db.get(ScrapeJob, job_id)
                                if job:
                                    job.current_page = page_index - 1
                                    job.total_bytes = total_bytes
                                    # progress is approximate: scraping = 80% of the work
                                    job.progress_pct = min(80.0, (page_index - 1) / max(1, max_pages) * 80.0)
                                    db.commit()

                        # Determine next URL
                        try:
                            next_url = await adapter.next_url(page, current_url, page_index - 1)
                        except Exception as e:  # noqa: BLE001
                            logger.warning("scraper_next_url_failed", error=str(e))
                            next_url = None
                    finally:
                        try:
                            await page.close()
                        except Exception:  # noqa: BLE001
                            pass

                    # Inter-page delay
                    delay = settings.scraper_default_delay_ms / 1000.0
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        return

                if not images:
                    self._mark_failed(job_id, "No images downloaded from any page")
                    return

                # Packaging
                with SessionLocal() as db:
                    job = db.get(ScrapeJob, job_id)
                    if job:
                        job.status = ScrapeJobStatus.PACKAGING
                        job.total_pages = len(images)
                        job.progress_pct = 85.0
                        db.commit()
                out_paths: dict[str, str] = {}
                for fmt in formats:
                    ext = {"PDF": "pdf", "EPUB": "epub", "CBZ": "cbz"}.get(fmt, fmt.lower())
                    out = settings.scraper_output_dir / str(job_id) / f"out.{ext}"
                    if fmt == "PDF":
                        await build_pdf(images, out)
                    elif fmt == "EPUB":
                        await build_epub(images, out, title=title)
                    elif fmt == "CBZ":
                        await build_cbz(images, out)
                    out_paths[fmt] = str(out)

                # Library import
                imported: dict[str, int] = {}
                if "library" in destinations:
                    from alejandria.services.scanner import get_scanner

                    scanner = get_scanner()
                    for fmt, p in out_paths.items():
                        try:
                            result = await scanner.add_book(Path(p))
                            bid = _re_find_calibre_id(result.get("stdout", ""))
                            if bid is not None:
                                imported[fmt] = bid
                            else:
                                # No id parsed, but the command may still have
                                # succeeded — log the stderr for diagnosis.
                                logger.warning(
                                    "scraper_import_no_id",
                                    fmt=fmt,
                                    stderr=result.get("stderr", "")[:500],
                                )
                        except Exception as e:  # noqa: BLE001
                            logger.error("scraper_import_failed", fmt=fmt, error=str(e))

                # Done
                with SessionLocal() as db:
                    job = db.get(ScrapeJob, job_id)
                    if not job:
                        return
                    job.status = ScrapeJobStatus.DONE
                    job.progress_pct = 100.0
                    job.completed_at = datetime.now(timezone.utc)
                    job.output_paths_json = json.dumps(out_paths)
                    if imported:
                        job.imported_book_ids_json = json.dumps(imported)
                    db.commit()
                logger.info("scraper_job_done", job_id=job_id, pages=len(images))

            except asyncio.CancelledError:
                self._mark_failed(job_id, "Cancelled by server shutdown")
                raise
            except Exception as e:  # noqa: BLE001
                logger.exception("scraper_job_error", job_id=job_id, error=str(e))
                self._mark_failed(job_id, str(e) or e.__class__.__name__)
            finally:
                self._tasks.pop(job_id, None)

    def _mark_failed(self, job_id: int, error: str) -> None:
        with SessionLocal() as db:
            job = db.get(ScrapeJob, job_id)
            if not job:
                return
            if job.status in (ScrapeJobStatus.DONE, ScrapeJobStatus.CANCELLED):
                return
            job.status = ScrapeJobStatus.FAILED
            job.error = error[:2000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()


_manager: ScraperManager | None = None


def get_scraper_manager() -> ScraperManager:
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = ScraperManager()
    return cast(ScraperManager, _manager)
