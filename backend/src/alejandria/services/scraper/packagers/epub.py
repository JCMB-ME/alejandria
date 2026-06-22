"""EPUB3 fixed-layout packager (ebooklib).

The resulting EPUB declares the EPUB3 rendition metadata:
  <meta property="rendition:layout">pre-paginated</meta>
  <meta property="rendition:orientation">auto</meta>
  <meta property="rendition:spread">none</meta>

Each page is a single XHTML <img> referencing one of the page-NNNN.jpg
files. The viewport width/height is derived from the first image's aspect
ratio (in em units, per the EPUB3 spec).
"""

from __future__ import annotations

import re
from pathlib import Path

from ebooklib import epub

from alejandria.services.scraper.image_fetch import FetchedImage


_IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif|bmp|tiff?)$", re.IGNORECASE)


def _img_filename(idx: int, hint: str) -> str:
    """Build a stable image filename like page-0001.jpg."""
    m = _IMG_EXT_RE.search(hint or "")
    ext = (m.group(1).lower() if m else "jpg")
    if ext == "jpeg":
        ext = "jpg"
    if ext == "tif":
        ext = "tiff"
    return f"page-{idx:04d}.{ext}"


async def build_epub(
    images: list[FetchedImage],
    out_path: Path,
    *,
    title: str = "Scraped Book",
    language: str = "en",
) -> Path:
    """Build a fixed-layout EPUB. Returns the output path."""
    if not images:
        raise ValueError("No images to package")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    book = epub.EpubBook()
    book.set_identifier("alejandria-scraper")
    book.set_title(title)
    book.set_language(language)
    book.add_author("Alejandría Scraper")

    # EPUB3 fixed-layout rendition metadata
    book.add_metadata(
        None,
        "meta",
        "pre-paginated",
        {"property": "rendition:layout"},
    )
    book.add_metadata(
        None,
        "meta",
        "auto",
        {"property": "rendition:orientation"},
    )
    book.add_metadata(
        None,
        "meta",
        "none",
        {"property": "rendition:spread"},
    )

    # Viewport sized from the first image
    first = images[0]
    width_px = first.width or 1200
    height_px = first.height or 1600
    aspect = height_px / max(width_px, 1)

    chapters: list[epub.EpubHtml] = []
    for idx, im in enumerate(images, start=1):
        filename = _img_filename(idx, im.filename_hint)
        # Add image as item
        img_item = epub.EpubItem(
            uid=f"img-{idx}",
            file_name=f"images/{filename}",
            media_type=im.content_type or "image/jpeg",
            content=im.bytes,
        )
        book.add_item(img_item)

        chapter = epub.EpubHtml(
            title=f"Page {idx}",
            file_name=f"page_{idx:04d}.xhtml",
            lang=language,
        )
        viewport_w = 1200
        viewport_h = int(viewport_w * aspect)
        chapter.content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops">\n'
            f'<head><title>Page {idx}</title>'
            f'<meta name="viewport" content="width={viewport_w}, height={viewport_h}"/>'
            f'</head>\n'
            f'<body><div style="margin:0;padding:0;text-align:center;">'
            f'<img src="images/{filename}" alt=""/>'
            f'</div></body></html>'
        ).encode("utf-8")
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    opts = {"spine_direction": False}
    epub.write_epub(str(out_path), book, opts)
    return out_path
