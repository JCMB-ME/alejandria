"""Abstract site adapter for the scraper.

An adapter knows how to:
  1. Match a URL (so the manager can pick the right adapter for a job).
  2. Fetch a single page in a Playwright browser, returning the candidate
     image URLs and any "next page" hint.
  3. Compute the URL of the next page (or None when the book ends).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class PageSnapshot:
    """Result of fetching a single page."""

    image_urls: list[str] = field(default_factory=list)
    next_url: str | None = None
    cookies_to_persist: dict[str, str] = field(default_factory=dict)
    headers_to_persist: dict[str, str] = field(default_factory=dict)
    # The URL we ended up on after any redirects. Differs from the
    # request URL when the site bounced us (session expired, rate
    # limited, captcha). The manager uses this to fail loudly with a
    # "session lost" error instead of silently marking the job done.
    final_url: str | None = None


@runtime_checkable
class SiteAdapter(Protocol):
    """Protocol every site adapter implements."""

    name: str

    def matches(self, url: str) -> bool: ...

    async def fetch_page(self, browser: object, url: str) -> PageSnapshot: ...

    async def next_url(
        self, page: object, current_url: str, page_index: int
    ) -> str | None: ...

    async def discover_title(
        self, browser: object, url: str
    ) -> str | None:
        """Best-effort title extraction from the chapter landing page.

        Returns the page's own title (e.g. "Manga X - Chapter 215") when
        the site exposes one, else None. The manager falls back to the
        user-supplied job title or "Scraped Book" if this returns None.
        """
        return None
