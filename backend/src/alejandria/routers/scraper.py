"""Web scraper API router."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from alejandria.auth.dependencies import get_current_user
from alejandria.db import get_db
from alejandria.models.scrape_job import ScrapeJobStatus
from alejandria.models.user import User
from alejandria.schemas.scraper import (
    AdapterTestRequest,
    AdapterTestResponse,
    ImageCandidate,
    NextCandidate,
    ScrapeJobCreate,
    ScrapeJobList,
    ScrapeJobRead,
)
from alejandria.services.scraper.manager import get_scraper_manager
from alejandria.services.scraper.ssrf import validate_url
from alejandria.utils.log import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _ensure_manager(request: Request):
    mgr = getattr(request.app.state, "scraper_manager", None)
    if mgr is None:
        mgr = get_scraper_manager()
        request.app.state.scraper_manager = mgr
    return mgr


@router.post("/jobs", response_model=ScrapeJobRead, status_code=201)
async def create_job(
    payload: ScrapeJobCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScrapeJobRead:
    mgr = await _ensure_manager(request)
    try:
        job = await mgr.submit(db, user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ScrapeJobRead.model_validate(job)


@router.get("/jobs", response_model=ScrapeJobList)
async def list_jobs(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScrapeJobList:
    mgr = await _ensure_manager(request)
    jobs = await mgr.list_jobs(db, user.id)
    return ScrapeJobList(items=[ScrapeJobRead.model_validate(j) for j in jobs])


@router.get("/jobs/{job_id}", response_model=ScrapeJobRead)
async def get_job(
    job_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScrapeJobRead:
    mgr = await _ensure_manager(request)
    job = await mgr.get_job(db, job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return ScrapeJobRead.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=ScrapeJobRead)
async def cancel_job(
    job_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScrapeJobRead:
    mgr = await _ensure_manager(request)
    try:
        job = await mgr.cancel(db, job_id, user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return ScrapeJobRead.model_validate(job)


@router.get("/jobs/{job_id}/download/{fmt}")
async def download_result(
    job_id: int,
    fmt: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    mgr = await _ensure_manager(request)
    job = await mgr.get_job(db, job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    if job.status != ScrapeJobStatus.DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done (status: {job.status.value})",
        )
    try:
        output_paths: dict[str, str] = json.loads(job.output_paths_json or "{}")
    except (TypeError, ValueError):
        output_paths = {}
    fmt_upper = fmt.upper()
    if fmt_upper not in output_paths:
        raise HTTPException(status_code=404, detail=f"No {fmt_upper} output for this job")
    path = Path(output_paths[fmt_upper])
    if not path.exists():
        raise HTTPException(status_code=410, detail="Output file no longer exists on disk")
    media = {
        "PDF": "application/pdf",
        "EPUB": "application/epub+zip",
        "CBZ": "application/vnd.comicbook+zip",
    }.get(fmt_upper, "application/octet-stream")
    safe_title = (job.title or f"scrape-{job_id}").replace("/", "_")[:80]
    filename = f"{safe_title}.{fmt.lower()}"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/adapters/test", response_model=AdapterTestResponse)
async def test_adapter(
    payload: AdapterTestRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> AdapterTestResponse:
    """Run a single page through the chosen adapter and report candidates.

    Does NOT persist any images or DB rows.
    """
    mgr = await _ensure_manager(request)
    try:
        url = validate_url(payload.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Ensure browser is up. This may take a few seconds the first time.
    await mgr._ensure_browser()  # noqa: SLF001
    if mgr._browser is None:  # noqa: SLF001
        raise HTTPException(status_code=503, detail="Browser unavailable")

    adapter = mgr._pick_adapter(url)  # noqa: SLF001
    if payload.adapter_name:
        for a in mgr._runtime_adapters:  # noqa: SLF001
            if a.name == f"yaml:{payload.adapter_name}":
                adapter = a
                break

    try:
        snapshot = await adapter.fetch_page(mgr._browser, url)  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Adapter fetch failed: {e}") from e

    # Pull image candidates with sizes by re-running the size inference
    image_candidates: list[ImageCandidate] = []
    for u in snapshot.image_urls:
        # We don't have dimensions from the snapshot; pass 0/0 placeholders.
        image_candidates.append(ImageCandidate(url=u, width=0, height=0))

    # Find next candidates by re-opening a page and asking for selectors
    next_candidates: list[NextCandidate] = []
    try:
        page = await mgr._browser.new_page()  # noqa: SLF001
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:  # noqa: BLE001
                pass
            data = await page.evaluate(
                """
                () => {
                  const out = [];
                  const selectors = ['a[rel~=next]', 'a.next', 'a[aria-label*=next i]', 'button.next'];
                  for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                      out.push({
                        selector: sel,
                        href: el.href || el.getAttribute('data-href') || null,
                        text: (el.textContent || '').trim().slice(0, 100) || null,
                      });
                    }
                  }
                  return out;
                }
                """
            )
            for entry in data or []:
                next_candidates.append(
                    NextCandidate(
                        selector=entry["selector"],
                        href=entry.get("href"),
                        text=entry.get("text"),
                    )
                )
        finally:
            try:
                await page.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        # Non-fatal — return what we have.
        pass

    return AdapterTestResponse(
        image_candidates=image_candidates,
        next_candidates=next_candidates,
        adapter_used=adapter.name,
    )
