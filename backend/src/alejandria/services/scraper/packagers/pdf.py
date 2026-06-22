"""PDF packager (img2pdf)."""

from __future__ import annotations

from pathlib import Path

import img2pdf

from alejandria.services.scraper.image_fetch import FetchedImage


async def build_pdf(images: list[FetchedImage], out_path: Path) -> Path:
    """Build a PDF from the given images. Returns the output path."""
    if not images:
        raise ValueError("No images to package")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout = img2pdf.get_layout_fun(
        pagesize=(
            (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))  # A4 portrait fallback
        )
    )
    data = [im.bytes for im in images]
    pdf_bytes = img2pdf.convert(data, layout_fun=layout)
    out_path.write_bytes(pdf_bytes)
    return out_path
