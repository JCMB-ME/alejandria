"""CBZ packager (stdlib zipfile).

Uses ZIP_STORED for JPEG/PNG/GIF/BMP (already compressed — DEFLATE wastes
CPU), and ZIP_DEFLATED for WebP and any other format.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from alejandria.services.scraper.image_fetch import FetchedImage


_IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif|bmp|tiff?)$", re.IGNORECASE)


def _img_filename(idx: int, hint: str) -> str:
    m = _IMG_EXT_RE.search(hint or "")
    ext = (m.group(1).lower() if m else "jpg")
    if ext == "jpeg":
        ext = "jpg"
    if ext == "tif":
        ext = "tiff"
    return f"page-{idx:04d}.{ext}"


async def build_cbz(images: list[FetchedImage], out_path: Path) -> Path:
    """Build a CBZ zip of the given images. Returns the output path."""
    if not images:
        raise ValueError("No images to package")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out_path, "w") as zf:
        for idx, im in enumerate(images, start=1):
            name = _img_filename(idx, im.filename_hint)
            ext = name.rsplit(".", 1)[-1].lower()
            compress = zipfile.ZIP_DEFLATED if ext == "webp" else zipfile.ZIP_STORED
            zf.writestr(
                zipfile.ZipInfo(name),
                im.bytes,
                compress_type=compress,
            )
    return out_path
