"""Streaming image fetcher with dimension + size caps.

The scraper MUST never allocate the full bitmap of an arbitrary image — a
single 50000x50000 px PNG would OOM the worker. We stream the response into
a BytesIO, ask Pillow to read ONLY the header (Image.open + .size), and
reject anything too big before handing the bytes to a packager.
"""

from __future__ import annotations

import imghdr
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlsplit

import aiohttp
from PIL import Image


@dataclass
class FetchedImage:
    """A downloaded page image."""

    bytes: bytes
    content_type: str
    width: int | None
    height: int | None
    bytes_on_wire: int
    filename_hint: str


_EXT_FOR_TYPE = {
    "jpeg": "jpg",
    "png": "png",
    "webp": "webp",
    "gif": "gif",
    "bmp": "bmp",
    "tiff": "tiff",
}


def _guess_ext(content_type: str, url: str, body: bytes) -> str:
    """Pick a sensible file extension."""
    if content_type:
        ct = content_type.lower().split(";", 1)[0].strip()
        if ct.startswith("image/"):
            short = ct.split("/", 1)[1]
            return _EXT_FOR_TYPE.get(short, short or "jpg")
    # Try Pillow's identification
    try:
        kind = imghdr.what(None, h=body)
        if kind:
            return _EXT_FOR_TYPE.get(kind, kind)
    except Exception:  # noqa: BLE001
        pass
    # Fall back to URL path
    path = urlsplit(url).path
    if "." in path.rsplit("/", 1)[-1]:
        return path.rsplit(".", 1)[-1].lower()[:8] or "jpg"
    return "jpg"


async def fetch_image(
    session: aiohttp.ClientSession,
    url: str,
    *,
    max_bytes: int = 50 * 1024 * 1024,
    max_dimension_px: int = 6000,
) -> FetchedImage:
    """Download an image into memory, validating size and dimensions.

    Raises ValueError on any cap violation. The bytes returned have NOT been
    decoded to a bitmap (Pillow only read the header).
    """
    buf = BytesIO()
    bytes_on_wire = 0
    content_type = ""
    async with session.get(url, allow_redirects=True) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            raise ValueError(
                f"Image too large: Content-Length {cl} > {max_bytes}"
            )
        async for chunk in resp.content.iter_chunked(64 * 1024):
            bytes_on_wire += len(chunk)
            if bytes_on_wire > max_bytes:
                raise ValueError(
                    f"Image exceeded max_bytes ({max_bytes}) during download"
                )
            buf.write(chunk)

    body = buf.getvalue()
    if not body:
        raise ValueError("Empty image body")

    width: int | None = None
    height: int | None = None
    try:
        with Image.open(BytesIO(body)) as im:
            width, height = im.size
    except Exception as e:  # noqa: BLE001
        # Not a parseable image — let the packager complain later.
        width = height = None
        if "cannot identify" not in str(e).lower() and "format" not in str(e).lower():
            raise ValueError(f"Could not parse image: {e}") from e

    if width is not None and height is not None:
        if width > max_dimension_px or height > max_dimension_px:
            raise ValueError(
                f"Image too large in pixels: {width}x{height} "
                f"(max {max_dimension_px} per axis)"
            )

    return FetchedImage(
        bytes=body,
        content_type=content_type or "image/jpeg",
        width=width,
        height=height,
        bytes_on_wire=bytes_on_wire,
        filename_hint=f"image.{_guess_ext(content_type, url, body)}",
    )
