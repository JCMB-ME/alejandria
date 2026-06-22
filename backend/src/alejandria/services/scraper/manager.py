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
    """Parse `calibredb add` stdout for the assigned book id.

    Calibre's CLI output is localized: English builds print
    "Added book ids: 1", Spanish builds print "ID de libros añadidos: 1".
    Accept any of the known phrasings by looking for a digit after a label
    that mentions book id(s), in any language.
    """
    patterns = (
        r"\badded book ids?[:\s=]+(\d+)",
        r"\bbook\s*ids?[:\s=]+(\d+)",
        r"id\s*de\s*libros?\s*añadidos?[:\s=]+(\d+)",
        r"id\s+de\s+libro\s+añadido[:\s=]+(\d+)",
    )
    for pat in patterns:
        m = re.search(pat, stdout, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None


def _safe_filename(name: str) -> str:
    """Sanitize a title for use as a filename.

    Strips characters Windows / macOS / Linux all reject, collapses
    whitespace, and caps the length. Used for the packager output path
    so the resulting book shows up in the library with its real name
    rather than a generic "out".
    """
    if not name:
        return "Scraped Book"
    # Replace any of: \ / : * ? " < > | | control chars
    s = re.sub(r'[\\/:|*?"<>\x00-\x1f]', "_", name)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 120:
        s = s[:120].rstrip()
    return s or "Scraped Book"


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
        """Return only *active* jobs for the user.

        The frontend panel is an in-flight monitor, not a history. A job that
        has reached a terminal state (DONE / FAILED / CANCELLED) is no longer
        the user's concern: the result already landed in the library, or the
        error was surfaced. Once the user navigates away or reloads, finished
        rows drop out of the panel automatically.
        """
        active_states = (
            ScrapeJobStatus.QUEUED,
            ScrapeJobStatus.SCRAPING,
            ScrapeJobStatus.PACKAGING,
        )
        stmt = (
            select(ScrapeJob)
            .where(
                ScrapeJob.user_id == user_id,
                ScrapeJob.status.in_(active_states),
            )
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

                # If the user didn't supply a title, try to discover one
                # from the chapter page itself. This runs once before the
                # main loop so the discovered title flows into the
                # packagers (EPUB metadata, PDF title, CBZ cover) without
                # a second page load.
                if not job.title or job.title.strip() in ("", "Scraped Book"):
                    try:
                        discovered = await adapter.discover_title(
                            self._browser, url
                        )
                        if discovered:
                            title = discovered
                            # Persist so /api/scraper/jobs shows it
                            with SessionLocal() as db:
                                j = db.get(ScrapeJob, job_id)
                                if j:
                                    j.title = title
                                    db.commit()
                            logger.info(
                                "scraper_title_discovered",
                                job_id=job_id,
                                title=title,
                            )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "scraper_title_discovery_failed", error=str(e)
                        )

                images: list[FetchedImage] = []
                page_index = 1
                current_url: str | None = url
                next_url: str | None = url
                total_bytes = 0
                max_bytes = settings.scraper_max_total_size_mb * 1024 * 1024
                max_pages = settings.scraper_max_pages_per_job
                # Track visited page URLs so a chapter-rolling-over "next"
                # link doesn't loop us into the next chapter's first page.
                visited_urls: set[str] = set()
                # Track image src URLs seen so far. Used to detect
                # "no new page content" — if every image on the current
                # page is already in this set, the chapter has rolled
                # over into a duplicate screen. Individual repeat images
                # (logos, footers shared across pages) are filtered but
                # don't stop the scrape.
                seen_image_srcs: set[str] = set()
                # Set by the inner loop when a repeat image is detected;
                # prevents adapter.next_url from overwriting the stop signal.
                stop_after_page = False

                while next_url and page_index <= max_pages:
                    # Cancel check
                    with SessionLocal() as db:
                        job = db.get(ScrapeJob, job_id)
                        if not job:
                            return
                        if job.status == ScrapeJobStatus.CANCELLED:
                            return
                        current_status = job.status
                    stop_after_page = False

                    # End-of-book detection: if the next URL is the same as
                    # one we already visited, the chapter has rolled over
                    # into the next one and the next page would be a repeat.
                    if next_url in visited_urls:
                        logger.info(
                            "scraper_end_of_book_detected",
                            job_id=job_id,
                            page=page_index,
                            next_url=next_url,
                        )
                        break
                    visited_urls.add(next_url)
                    if current_status == ScrapeJobStatus.CANCELLED:
                        return

                    current_url = next_url
                    snapshot: PageSnapshot = await adapter.fetch_page(self._browser, current_url)
                    if not snapshot.image_urls:
                        # No images — either a bad page or end of book.
                        # Distinguish "session lost" (the site redirected
                        # us away from the chapter — token expired or
                        # rate limited) from "we ran past the end of the
                        # chapter". The former should fail loudly so the
                        # user knows to re-authenticate.
                        #
                        # Heuristic: if the chapter id is in the requested
                        # URL but not in the final URL after the fetch,
                        # the site kicked us out. We also check for a
                        # redirect to a non-chapter path (e.g. the site
                        # homepage, a login screen).
                        chapter_id = ""
                        if "chapter=" in url:
                            chapter_id = url.split("chapter=", 1)[1].split("&", 1)[0]
                        bounced = (
                            snapshot.final_url is not None
                            and (
                                ("chapter=" in url and "chapter=" not in snapshot.final_url)
                                or (
                                    chapter_id
                                    and chapter_id not in snapshot.final_url
                                )
                                or snapshot.final_url.rstrip("/").endswith(
                                    ("/yupmanga.com", "yupmanga.com/")
                                )
                            )
                        )
                        if bounced:
                            msg = (
                                f"Session lost on page {page_index}: site "
                                f"redirected to {snapshot.final_url}. "
                                f"Re-authenticate and retry."
                            )
                            logger.warning(
                                "scraper_session_lost",
                                job_id=job_id,
                                page=page_index,
                                final_url=snapshot.final_url,
                            )
                            with SessionLocal() as db:
                                job = db.get(ScrapeJob, job_id)
                                if job:
                                    job.status = ScrapeJobStatus.FAILED
                                    job.error = msg
                                    job.completed_at = datetime.now(timezone.utc)
                                    db.commit()
                            return
                        break

                    # Re-open a page for the next_url computation. We need a
                    # fresh Page because the adapter may have closed it.
                    page = await self._browser.new_page()
                    try:
                        await page.goto(current_url, wait_until="domcontentloaded", timeout=30_000)
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=5_000)
                        except Exception:  # noqa: BLE001
                            pass

                        # Filter out image srcs we've already collected.
                        # Batched up front so we can fan out the actual
                        # fetches in parallel.
                        #
                        # IMPORTANT: only stop the WHOLE scrape if this page
                        # has zero new images. The previous logic stopped
                        # on the first repeat, which is wrong for sites that
                        # share decorative chrome (logos, headers, footer
                        # banners) across every page — page 2's chrome image
                        # would be flagged as a repeat and we'd stop at page
                        # 29 instead of 215. The signal we actually want is
                        # "no new page content here", which means either an
                        # empty snapshot (already handled above) or every
                        # image on this page was seen before — i.e. the
                        # chapter rolled over into a duplicate screen.
                        new_image_urls: list[str] = []
                        repeats_on_page = 0
                        for img_url in snapshot.image_urls:
                            if img_url in seen_image_srcs:
                                repeats_on_page += 1
                                continue
                            seen_image_srcs.add(img_url)
                            new_image_urls.append(img_url)

                        if (
                            repeats_on_page
                            and not new_image_urls
                        ):
                            # Every image on this page is one we've already
                            # collected. The chapter has likely rolled over
                            # into a cover/landing screen.
                            logger.info(
                                "scraper_duplicate_page_detected",
                                job_id=job_id,
                                page=page_index,
                                repeats=repeats_on_page,
                            )
                            stop_after_page = True
                        elif repeats_on_page:
                            # Partial repeat — usually decorative chrome.
                            # Log it for telemetry but keep going.
                            logger.info(
                                "scraper_partial_repeat_skipped",
                                job_id=job_id,
                                page=page_index,
                                repeats=repeats_on_page,
                                fresh=len(new_image_urls),
                            )

                        if not new_image_urls:
                            # Nothing to fetch — either already seen or empty page.
                            pass
                        else:
                            # Fetch images in parallel chunks. The previous
                            # serial loop dominated wall time on long chapters
                            # (a 215-page manga spent most of its budget
                            # waiting on 215 sequential image GETs).
                            image_concurrency = max(1, settings.scraper_image_concurrency)
                            for chunk_start in range(0, len(new_image_urls), image_concurrency):
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
                                chunk = new_image_urls[chunk_start : chunk_start + image_concurrency]
                                results = await asyncio.gather(
                                    *(fetch_image(self._http_session, u) for u in chunk),
                                    return_exceptions=True,
                                )
                                for img_url, fetched_or_exc in zip(chunk, results):
                                    if isinstance(fetched_or_exc, Exception):
                                        if isinstance(fetched_or_exc, ValueError):
                                            logger.warning(
                                                "scraper_image_skipped",
                                                url=img_url,
                                                error=str(fetched_or_exc),
                                            )
                                        else:
                                            logger.warning(
                                                "scraper_image_error",
                                                url=img_url,
                                                error=str(fetched_or_exc),
                                            )
                                        continue
                                    fetched = fetched_or_exc
                                    page_filename = pages_dir / (
                                        f"page-{page_index:04d}."
                                        f"{fetched.filename_hint.rsplit('.', 1)[-1] or 'jpg'}"
                                    )
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
                                        job.progress_pct = min(
                                            80.0,
                                            (page_index - 1) / max(1, max_pages) * 80.0,
                                        )
                                        db.commit()

                        # Determine next URL
                        if stop_after_page:
                            next_url = None
                        else:
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
                # Use the discovered title (or user-supplied title) for the
                # output filename. Previously this was hardcoded to "out"
                # which made every scrape show up as "out - Desconocido"
                # in the library — useless for browsing.
                safe_title = _safe_filename(title or "Scraped Book")
                for fmt in formats:
                    ext = {"PDF": "pdf", "EPUB": "epub", "CBZ": "cbz"}.get(fmt, fmt.lower())
                    out = settings.scraper_output_dir / str(job_id) / f"{safe_title}.{ext}"
                    if fmt == "PDF":
                        await build_pdf(images, out, title=title)
                    elif fmt == "EPUB":
                        await build_epub(images, out, title=title)
                    elif fmt == "CBZ":
                        await build_cbz(images, out)
                    out_paths[fmt] = str(out)

                # Library import — every successful scrape is auto-imported.
                # `download` is a no-op (the file is already on disk and the
                # browser fetch is one-shot); library is the only meaningful
                # destination and is always on.
                imported: dict[str, int] = {}
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
