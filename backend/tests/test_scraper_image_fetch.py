"""Tests for the streaming image fetcher (size + dimension caps)."""

from __future__ import annotations

import io

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from PIL import Image

from alejandria.services.scraper.image_fetch import fetch_image


def _png_bytes(w: int, h: int) -> bytes:
    im = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest_asyncio.fixture
async def image_server():
    """A tiny aiohttp server that serves a 10 KB PNG and a 7000x7000 PNG."""
    async def small(request: web.Request) -> web.Response:
        return web.Response(body=_png_bytes(100, 100), content_type="image/png")

    async def huge(request: web.Request) -> web.Response:
        return web.Response(body=_png_bytes(7000, 7000), content_type="image/png")

    app = web.Application()
    app.router.add_get("/small.png", small)
    app.router.add_get("/huge.png", huge)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    # Discover the port
    server = site._server  # type: ignore[attr-defined]
    sockets = list(server.sockets)
    port = sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    yield base
    await runner.cleanup()


@pytest.mark.asyncio
async def test_fetches_small_image(image_server: str):
    async with aiohttp.ClientSession() as session:
        f = await fetch_image(
            session, f"{image_server}/small.png", allow_loopback=True,
        )
    assert f.width == 100
    assert f.height == 100
    assert f.content_type == "image/png"
    assert len(f.bytes) > 0


@pytest.mark.asyncio
async def test_rejects_huge_dimensions(image_server: str):
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ValueError) as exc:
            await fetch_image(
                session,
                f"{image_server}/huge.png",
                max_dimension_px=6000,
                allow_loopback=True,
            )
    assert "too large" in str(exc.value).lower() or "pixels" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_fetch_image_rejects_redirect_to_private_ip():
    """fetch_image must reject a 302 redirect to a private IP."""
    async def redirect_handler(request: web.Request) -> web.Response:
        return web.Response(status=302, headers={"Location": "http://192.168.1.1/admin"})

    app = web.Application()
    app.router.add_get("/img.jpg", redirect_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    try:
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ValueError):
                await fetch_image(
                    session,
                    f"http://127.0.0.1:{port}/img.jpg",
                    max_bytes=1024 * 1024,
                    allow_loopback=True,
                )
    finally:
        await runner.cleanup()

