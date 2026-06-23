"""Cover extraction and caching."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from alejandria.config import get_settings
from alejandria.services.calibre_db import get_calibre_db
from alejandria.utils.log import get_logger

logger = get_logger(__name__)

# Cover size variants (width in pixels)
COVER_SIZES = {
    "thumb": 200,
    "small": 400,
    "medium": 800,
    "large": 1600,
    "original": 0,  # no resize
}


def cover_cache_path(book_id: int, size: str = "medium") -> Path:
    """Get the path to a cached cover image."""
    settings = get_settings()
    width = COVER_SIZES.get(size, 800)
    suffix = "orig" if width == 0 else str(width)
    return settings.caches_path / "covers" / str(book_id) / f"{suffix}.jpg"


def extract_cover_from_file(file_path: Path) -> bytes | None:
    """Extract cover image bytes from a book file."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".epub":
            return _extract_epub_cover(file_path)
        if suffix == ".pdf":
            return _extract_pdf_cover(file_path)
        if suffix in (".mobi", ".azw3", ".azw"):
            return _extract_mobi_cover(file_path)
        if suffix in (".fb2", ".djvu", ".rtf", ".docx", ".html", ".txt"):
            # Use Calibre's metadata extraction
            return _extract_via_calibre(file_path)
    except Exception as e:
        logger.debug("cover_extract_failed", path=str(file_path), error=str(e))
    return None


def _extract_epub_cover(file_path: Path) -> bytes | None:
    """Extract cover from EPUB (zip archive)."""
    import zipfile

    with zipfile.ZipFile(file_path) as zf:
        # Find cover in OPF metadata
        # Look for common cover paths first
        cover_candidates = [
            n for n in zf.namelist()
            if n.lower().endswith((".jpg", ".jpeg", ".png"))
            and any(s in n.lower() for s in ("cover", "title", "front"))
        ]
        # If no obvious cover, pick first image
        if not cover_candidates:
            cover_candidates = [
                n for n in zf.namelist()
                if n.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
        if not cover_candidates:
            return None
        # Prefer .jpg, then .png
        cover_candidates.sort(key=lambda n: (not n.lower().endswith(".jpg"), n))
        return zf.read(cover_candidates[0])


def _extract_pdf_cover(file_path: Path) -> bytes | None:
    """Extract first page as cover from PDF."""
    try:
        import pypdf

        reader = pypdf.PdfReader(str(file_path))
        if not reader.pages:
            return None
        page = reader.pages[0]
        for img in page.images:
            return img.data
    except Exception as e:
        logger.debug("pdf_cover_failed", error=str(e))
    # Fallback: use PyMuPDF for rendering
    try:
        import fitz

        doc = fitz.open(str(file_path))
        if not doc.page_count:
            return None
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        return pix.tobytes("jpg")
    except Exception as e:
        logger.debug("pdf_cover_mupdf_failed", error=str(e))
    return None


def _extract_mobi_cover(file_path: Path) -> bytes | None:
    """Extract cover from MOBI/AZW3."""
    try:
        from mobi import Mobi

        book = Mobi(str(file_path))
        # First image record
        for record in book.records if hasattr(book, "records") else []:
            if record.get("type") == "image":
                return record.get("data")
    except Exception as e:
        logger.debug("mobi_cover_failed", error=str(e))
    return _extract_via_calibre(file_path)


def _extract_via_calibre(file_path: Path) -> bytes | None:
    """Use Calibre's ebook-meta to extract cover."""
    import shutil
    import subprocess
    import tempfile

    settings = get_settings()
    if not settings.enable_calibre:
        return None
    # Resolve ebook-meta next to calibredb (or in PATH).
    # Docker installs to /opt/calibre; Windows MSI installs elsewhere.
    calibredb = settings.calibre_bin_path
    bin_dir = Path(calibredb).parent if Path(calibredb).is_absolute() else None
    candidates = []
    if bin_dir:
        candidates.append(str(bin_dir / ("ebook-meta.exe" if settings.caches_path.drive else "ebook-meta")))
    candidates.extend(["ebook-meta", "/opt/calibre/ebook-meta"])
    ebook_meta = next((c for c in candidates if shutil.which(c) or Path(c).exists()), None)
    if not ebook_meta:
        return None
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        try:
            cmd = [ebook_meta, str(file_path), "--get-cover", tmp.name]
            proc = subprocess.run(cmd, capture_output=True, timeout=30)
            if proc.returncode == 0 and Path(tmp.name).exists() and Path(tmp.name).stat().st_size > 0:
                return Path(tmp.name).read_bytes()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
    return None


def get_cover(book_id: int, size: str = "medium") -> bytes | None:
    """Get cover image bytes, extracting and caching if needed."""
    cache = cover_cache_path(book_id, size)
    if cache.exists():
        return cache.read_bytes()

    calibre = get_calibre_db()
    fmt_path = calibre.get_first_format(book_id)
    if not fmt_path:
        return None
    fmt, path = fmt_path

    # Try reading cover.jpg directly from the book folder first (Calibre extracts it by default)
    cover_file = path.parent / "cover.jpg"
    if cover_file.exists():
        raw = cover_file.read_bytes()
    else:
        raw = extract_cover_from_file(path)

    if not raw:
        return None

    # Resize if needed
    target_w = COVER_SIZES.get(size, 0)
    if target_w > 0:
        try:
            img = Image.open(io.BytesIO(raw))
            if img.width > target_w:
                ratio = target_w / img.width
                new_h = int(img.height * ratio)
                img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            raw = buf.getvalue()
        except Exception as e:
            logger.warning("cover_resize_failed", error=str(e))

    # Save to cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return raw
