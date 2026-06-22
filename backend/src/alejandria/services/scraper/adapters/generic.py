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
            except Exception:  # noqa: BLE001
                pass
            candidates = await page.evaluate(
                """
                () => {
                  const out = [];
                  document.querySelectorAll('img').forEach(im => {
                    const r = im.getBoundingClientRect();
                    const w = im.naturalWidth || r.width;
                    const h = im.naturalHeight || r.height;
                    if (w >= 200 && h >= 200) out.push({src: im.src, w, h});
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
            return PageSnapshot(
                image_urls=[c["src"] for c in (candidates or []) if c.get("src")]
            )
        finally:
            try:
                await page.close()
            except Exception:  # noqa: BLE001
                pass

    async def next_url(
        self, page: Any, current_url: str, page_index: int
    ) -> str | None:
        """Try, in order: rel=next, text match, URL increment, hash change.

        Each candidate href is checked against ``current_url``'s path. If
        the candidate points to a different page on the same site (e.g.
        site-wide pagination that says "Siguiente" but actually points to
        the listing page, not the next chapter page), it's rejected.
        """
        from urllib.parse import urlparse

        current_path = urlparse(current_url).path

        def _same_context(candidate: str | None) -> str | None:
            if not candidate:
                return None
            try:
                cand_path = urlparse(candidate).path
            except (ValueError, TypeError):
                return None
            # Accept if the candidate path is the same as the current
            # path, or if it shares the same filename (last segment),
            # or if the current path is '/' (root index page).
            if not current_path or current_path == "/":
                return candidate
            if cand_path == current_path:
                return candidate
            cur_leaf = current_path.rsplit("/", 1)[-1]
            cand_leaf = cand_path.rsplit("/", 1)[-1]
            if cur_leaf and cur_leaf == cand_leaf:
                return candidate
            return None

        # 1. <a rel="next"> href
        try:
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
        except Exception:  # noqa: BLE001
            pass

        # 2. link by text content
        try:
            text_href = await page.evaluate(
                """
                () => {
                  const links = Array.from(document.querySelectorAll('a'));
                  for (const a of links) {
                    const t = (a.textContent || '').trim();
                    if (/^(next|siguiente|next\\s+page|siguiente\\s+p[áa]gina|→|›|>)$/i.test(t)) {
                      return a.href;
                    }
                  }
                  return null;
                }
                """
            )
            candidate = _same_context(text_href)
            if candidate:
                return candidate
        except Exception:  # noqa: BLE001
            pass

        # 3. URL increment — trailing /N where N == page_index
        m = re.search(r"/(\d+)/?$", current_url)
        if m:
            try:
                n = int(m.group(1))
                if n == page_index:
                    candidate = current_url[: m.start(1)] + str(n + 1) + current_url[m.end(1):]
                    return candidate
            except (ValueError, IndexError):
                pass

        # 3b. Query-param ?page=N increment
        m = re.search(r"([?&])page=(\d+)\b", current_url)
        if m:
            try:
                n = int(m.group(2))
                if n == page_index:
                    sep = "&" if m.group(1) == "&" else "?"
                    new_n = n + 1
                    return current_url[: m.start(2)] + str(new_n) + current_url[m.end(2):]
            except (ValueError, IndexError):
                pass

        # 4. hash change after scroll — best-effort
        return None
