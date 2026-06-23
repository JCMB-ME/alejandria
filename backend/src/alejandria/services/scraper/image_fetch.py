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
from urllib.parse import urljoin, urlsplit

import aiohttp
from PIL import Image

from alejandria.services.scraper.ssrf import validate_url


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
    except Exception:
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
    allow_loopback: bool = False,
) -> FetchedImage:
    """Download an image into memory, validating size and dimensions.

    Raises ValueError on any cap violation. The bytes returned have NOT been
    decoded to a bitmap (Pillow only read the header).

    `allow_loopback` is False in production. Tests that spin up a local
    aiohttp fixture on 127.0.0.1 must pass True.
    """
    # Strip ``&context=...`` (and similar YupManga quirks) before hitting
    # the network. YupManga's reader renders page 30 with an image src
    # like ``image-proxy-v2.php?chapter=X&page=30&token=Y&context=r`` —
    # the ``context=r`` query parameter is a client-side hint only, and
    # the proxy returns 403 ``Invalid context`` when it's present. The
    # actual panel image is downloadable from the same URL minus that
    # parameter. Stripping here means we don't need to special-case
    # YupManga in the adapter — the URL the browser hands us works
    # after this one normalisation. Other ``&foo=bar`` junk that the
    # proxy might tolerate is left alone.
    if "context=" in url:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        kept = [
            (k, v)
            for (k, v) in parse_qsl(parts.query, keep_blank_values=True)
            if k != "context"
        ]
        url = urlunsplit(
            parts._replace(query=urlencode(kept, doseq=True))
        )
    buf = BytesIO()
    bytes_on_wire = 0
    content_type = ""
    # Validate the initial URL.
    current_url = validate_url(url, allow_loopback=allow_loopback)
    # Manual redirect loop so we re-run SSRF validation on every Location.
    MAX_REDIRECTS = 5
    for _ in range(MAX_REDIRECTS + 1):
        async with session.get(current_url, allow_redirects=False) as resp:
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise ValueError(f"Redirect with no Location header from {current_url}")
                # Resolve relative redirects and re-validate.
                current_url = validate_url(
                    urljoin(current_url, location), allow_loopback=allow_loopback,
                )
                continue
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
            break
    else:
        raise ValueError(f"Too many redirects from {url}")

    body = buf.getvalue()
    if not body:
        raise ValueError("Empty image body")

    width: int | None = None
    height: int | None = None
    try:
        with Image.open(BytesIO(body)) as im:
            width, height = im.size
    except Exception as e:
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
