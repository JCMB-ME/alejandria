"""Tests for the three packagers (PDF, EPUB, CBZ)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from alejandria.services.scraper.image_fetch import FetchedImage
from alejandria.services.scraper.packagers.cbz import build_cbz
from alejandria.services.scraper.packagers.epub import build_epub
from alejandria.services.scraper.packagers.pdf import build_pdf


def _png(w: int = 200, h: int = 300) -> bytes:
    from PIL import Image

    im = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _imgs(n: int = 2) -> list[FetchedImage]:
    return [
        FetchedImage(
            bytes=_png(),
            content_type="image/png",
            width=200,
            height=300,
            bytes_on_wire=0,
            filename_hint="image.png",
        )
        for _ in range(n)
    ]


@pytest.mark.asyncio
async def test_pdf_built(tmp_path: Path):
    out = tmp_path / "out.pdf"
    p = await build_pdf(_imgs(3), out)
    assert p.exists()
    assert p.stat().st_size > 0
    # Quick magic check
    assert p.read_bytes()[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_epub_built_with_rendition_metadata(tmp_path: Path):
    out = tmp_path / "out.epub"
    p = await build_epub(_imgs(2), out, title="Hello")
    assert p.exists()
    assert p.stat().st_size > 0
    # EPUB is a zip; find the OPF and check rendition metadata
    with zipfile.ZipFile(p) as z:
        opf_names = [n for n in z.namelist() if n.endswith(".opf")]
        assert opf_names
        opf = z.read(opf_names[0]).decode("utf-8")
    assert "rendition:layout" in opf
    assert "pre-paginated" in opf


@pytest.mark.asyncio
async def test_cbz_built(tmp_path: Path):
    out = tmp_path / "out.cbz"
    p = await build_cbz(_imgs(4), out)
    assert p.exists()
    assert p.stat().st_size > 0
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
    assert any(n.startswith("page-") for n in names)


@pytest.mark.asyncio
async def test_empty_raises(tmp_path: Path):
    out = tmp_path / "out.pdf"
    with pytest.raises(ValueError):
        await build_pdf([], out)
