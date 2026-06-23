"""YAML-driven site adapter loader."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from alejandria.services.scraper.adapters.base import PageSnapshot
from alejandria.services.scraper.adapters.generic import GenericAdapter

PaginationStyle = Literal["click", "url_increment", "infinite_scroll"]


@dataclass
class YamlAdapter:
    """Raw configuration for a YAML-defined site adapter."""

    name: str
    url_regex: str
    image_selector: str = "img.large, #page-img"
    next_selector: str | None = None
    pagination_style: PaginationStyle = "click"
    delay_ms_between_requests: int = 500
    user_agent: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    requires_auth: bool = False

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.url_regex)


@dataclass
class _RuntimeYamlAdapter:
    """Adapter object that wraps a YamlAdapter for the manager."""

    raw: YamlAdapter
    pattern: re.Pattern[str]

    @property
    def name(self) -> str:
        return f"yaml:{self.raw.name}"

    def matches(self, url: str) -> bool:
        return bool(self.pattern.search(url))

    async def fetch_page(self, browser: Any, url: str) -> PageSnapshot:
        page = await browser.new_page()
        try:
            if self.raw.user_agent:
                await page.set_extra_http_headers({"User-Agent": self.raw.user_agent})
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            imgs: list[str] = await page.evaluate(
                """
                (sel) => Array.from(document.querySelectorAll(sel))
                  .map(el => el.src || el.getAttribute('data-src'))
                  .filter(Boolean)
                """,
                self.raw.image_selector,
            )
            return PageSnapshot(
                image_urls=imgs,
                headers_to_persist=self.raw.headers,
                cookies_to_persist=self.raw.cookies,
            )
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def next_url(
        self, page: Any, current_url: str, page_index: int
    ) -> str | None:
        if self.raw.next_selector:
            try:
                href = await page.evaluate(
                    """
                    (sel) => {
                      const el = document.querySelector(sel);
                      return el ? (el.href || el.getAttribute('data-href') || null) : null;
                    }
                    """,
                    self.raw.next_selector,
                )
                if href:
                    return href
            except Exception:
                pass
        if self.raw.pagination_style == "url_increment":
            m = re.search(r"/(\d+)/?$", current_url)
            if m:
                try:
                    n = int(m.group(1))
                    if n == page_index:
                        return current_url[: m.start(1)] + str(n + 1) + current_url[m.end(1):]
                except (ValueError, IndexError):
                    pass
        return None


def load_yaml_adapters(path: Path) -> list[YamlAdapter]:
    """Load YamlAdapter entries from a YAML file. Returns [] if the file is
    missing or empty. Raises ValueError on schema problems."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e
    raw_adapters: list[dict[str, Any]] = data.get("adapters") or []
    out: list[YamlAdapter] = []
    for entry in raw_adapters:
        try:
            out.append(
                YamlAdapter(
                    name=str(entry["name"]),
                    url_regex=str(entry["url_regex"]),
                    image_selector=entry.get("image_selector", "img.large, #page-img"),
                    next_selector=entry.get("next_selector"),
                    pagination_style=entry.get("pagination_style", "click"),
                    delay_ms_between_requests=int(entry.get("delay_ms_between_requests", 500)),
                    user_agent=entry.get("user_agent"),
                    cookies=entry.get("cookies") or {},
                    headers=entry.get("headers") or {},
                    requires_auth=bool(entry.get("requires_auth", False)),
                )
            )
        except KeyError as e:
            raise ValueError(f"Adapter missing required key {e}") from e
    return out


def compile_yaml_adapters(
    raw: list[YamlAdapter],
) -> list[_RuntimeYamlAdapter]:
    return [
        _RuntimeYamlAdapter(r, r.compiled())
        for r in raw
    ]


__all__ = [
    "GenericAdapter",
    "PaginationStyle",
    "YamlAdapter",
    "compile_yaml_adapters",
    "load_yaml_adapters",
]
