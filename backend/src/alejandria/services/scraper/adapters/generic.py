"""Default heuristic site adapter.

Picks the largest <img> on the page, then tries several common "next" patterns.
This is intentionally conservative — better to stop with one page than to
loop forever on the wrong URL.
"""

from __future__ import annotations

import re
from typing import Any

from alejandria.services.scraper.adapters.base import PageSnapshot

_NEXT_TEXT_RE = re.compile(
    r"^(next|siguiente|siguiente\s+p[áa]gina|next\s+page|→|>)",
    re.IGNORECASE,
)


class GenericAdapter:
    """Heuristic adapter — last-resort fallback."""

    name = "generic"

    def matches(self, url: str) -> bool:
        return True  # last-resort

    async def fetch_page(self, browser: Any, url: str) -> PageSnapshot:
        """Use Playwright to load the page and pick the largest images."""
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                # Networkidle can hang for 15s on a manga page with
                # dozens of in-flight image requests. domcontentloaded
                # is plenty — images stream in after.
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass
            candidates = await page.evaluate(
                """
                () => {
                  const out = [];
                  document.querySelectorAll('img').forEach(im => {
                    const r = im.getBoundingClientRect();
                    const w = im.naturalWidth || r.width;
                    const h = im.naturalHeight || r.height;
                    // Accept if the image has loaded AND is large enough
                    // to be a panel. The ``200x200`` floor is to skip
                    // decorative chrome (logos, header banners) — those
                    // are tiny and re-appear on every page.
                    //
                    // ALSO accept images whose natural dimensions we
                    // can't read yet (naturalWidth=0). On YupManga's page
                    // 30 the <img> src contains ``&context=r`` which
                    // the proxy rejects with 403, so the browser leaves
                    // naturalWidth at 0. The image is still valid —
                    // fetch_image strips ``&context=`` and downloads it
                    // fine. Without this fallback the scraper silently
                    // stops at page 30 because the candidate is
                    // rejected here.
                    if ((w >= 200 && h >= 200) || (w === 0 && h === 0 && im.src)) {
                      out.push({src: im.src, w, h});
                    }
                  });
                  document.querySelectorAll('*').forEach(el => {
                    const bg = getComputedStyle(el).backgroundImage;
                    const m = bg.match(/url\\(['\"]?([^'\")]+)['\"]?\\)/);
                    if (m) out.push({src: m[1], w: el.clientWidth, h: el.clientHeight});
                  });
                  return out.sort((a, b) => (b.w * b.h) - (a.w * a.h)).slice(0, 10);
                }
                """
            )
            # Capture the URL we ended up on after any redirects so the
            # manager can detect a "session lost" bounce (rate limit,
            # token expiry) and fail loudly instead of silently ending.
            final_url = page.url
            return PageSnapshot(
                image_urls=[c["src"] for c in (candidates or []) if c.get("src")],
                final_url=final_url,
            )
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def discover_title(
        self, browser: Any, url: str
    ) -> str | None:
        """Best-effort chapter title extraction.

        Manga sites usually put "Manga Name - Chapter 215 :: Site Name"
        in <title> and a cleaner label in the first <h1>. We try <h1>
        first (shorter, less noisy) and fall back to <title> with
        common ":: Site" / "- Site Name" suffixes stripped.
        """
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass
            title = await page.evaluate(
                """
                () => {
                  const h1 = document.querySelector('h1');
                  if (h1 && h1.textContent && h1.textContent.trim()) {
                    return h1.textContent.trim();
                  }
                  const og = document.querySelector('meta[property="og:title"]');
                  if (og && og.content && og.content.trim()) {
                    return og.content.trim();
                  }
                  const t = document.querySelector('title');
                  if (t && t.textContent && t.textContent.trim()) {
                    // Strip common " :: Site", " - Site", " | Site" suffixes
                    return t.textContent
                      .trim()
                      .split(/\\s*(?:::|\\||\\—|\\–|-)\\s+[A-Za-z][^|::\\-]+$/)[0]
                      .trim();
                  }
                  return null;
                }
                """
            )
            if not title:
                return None
            # Cap absurd lengths (some sites put the entire chapter in <title>).
            if len(title) > 200:
                title = title[:200].rstrip() + "…"
            return title
        except Exception:
            return None
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def next_url(
        self, page: Any, current_url: str, page_index: int
    ) -> str | None:
        """Compute the URL for the next page.

        Strategy order matters here. URL increment is the deterministic,
        trust-the-server approach: if the current URL is
        ``...?page=29``, we know with certainty that ``...?page=30`` is
        the next page. Falling back to DOM-mined "Siguiente" / rel=next
        links comes second because those links have proven flaky on
        YupManga — at chapter boundaries they can point to the next
        chapter's first page, or back to the listing page, breaking the
        loop at exactly the wrong moment.

        The previous strict ``n == page_index`` check on the increment
        strategies was a load-bearing sanity check, but it doubled as a
        silent killer: if the URL and the loop counter ever got out of
        sync for any reason (a redirect rewrote ``?page=N`` to ``?page=1``
        + anchor, or the session token in the URL changed but page_index
        didn't), the increment returned ``None`` and the loop exited
        cleanly with N-1 pages — which is the "stopped at page 29"
        symptom the user kept hitting. The increment now just bumps the
        trailing number we find, regardless of the manager's internal
        counter, and trusts ``visited_urls`` in the manager to catch
        genuine loops.

        Args:
            current_url: the URL we just fetched. Used as the seed for
                the increment.
            page_index: the manager's page counter (0-indexed at this
                point — it was already incremented after the save).
                Kept for backwards compatibility with adapter overrides;
                not used for any logic now.

        Returns:
            The next URL, or ``None`` if no recognisable page parameter
            is present in ``current_url`` (sites that don't use any
            URL-based pagination need an adapter override).
        """
        del page_index  # see docstring — we no longer gate on this

        # 1. ?page=N (or &page=N) — YupManga, most modern manga readers.
        m = re.search(r"([?&])page=(\d+)\b", current_url)
        if m:
            try:
                n = int(m.group(2))
                new_n = n + 1
                return (
                    current_url[: m.start(2)]
                    + str(new_n)
                    + current_url[m.end(2):]
                )
            except (ValueError, IndexError):
                pass

        # 2. trailing /N — older sites that serve chapter pages as
        # /manga/.../1, /manga/.../2 etc.
        m = re.search(r"/(\d+)/?$", current_url)
        if m:
            try:
                n = int(m.group(1))
                return (
                    current_url[: m.start(1)]
                    + str(n + 1)
                    + current_url[m.end(1):]
                )
            except (ValueError, IndexError):
                pass

        # 3. rel=next on the rendered page. Used as a last resort only —
        # the DOM-mined link can point to a different chapter, the
        # chapter listing, or the homepage, any of which would break the
        # scrape at the chapter boundary. The manager's chapter-id
        # boundary check catches and rejects cross-chapter jumps.
        try:
            from urllib.parse import urlparse

            current_path = urlparse(current_url).path

            def _same_context(candidate: str | None) -> str | None:
                if not candidate:
                    return None
                try:
                    cand_path = urlparse(candidate).path
                except (ValueError, TypeError):
                    return None
                if not current_path or current_path == "/":
                    return candidate
                if cand_path == current_path:
                    return candidate
                cur_leaf = current_path.rsplit("/", 1)[-1]
                cand_leaf = cand_path.rsplit("/", 1)[-1]
                if cur_leaf and cur_leaf == cand_leaf:
                    return candidate
                return None

            next_href = await page.evaluate(
                """
                () => {
                  const a = document.querySelector('a[rel~="next"]');
                  return a ? a.href : null;
                }
                """
            )
            candidate = _same_context(next_href)
            if candidate:
                return candidate
        except Exception:
            pass

        # 4. hash change after scroll — best-effort
        return None
