"""OPDS 1.2 catalog.

Provides OPDS feeds for compatibility with KOReader, Calibre Companion,
Moon+ Reader, iOS reader apps, etc.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session


class XMLResponse(FastAPIResponse):
    """Minimal XML response (FastAPI doesn't ship one)."""

    media_type = "application/xml"

    def render(self, content: bytes) -> bytes:
        return content

from alejandria.auth.dependencies import get_optional_user
from alejandria.config import get_settings
from alejandria.db import get_db
from alejandria.models.user import User
from alejandria.services.calibre_db import get_calibre_db

router = APIRouter()

ATOM_NS = "http://www.w3.org/2005/Atom"
OPDS_NS = "http://opds-spec.org/2010/catalog"
DC_NS = "http://purl.org/dc/terms/"
DCTERMS_NS = "http://purl.org/dc/terms/"

ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("opds", OPDS_NS)
ET.register_namespace("dc", DC_NS)


def _feed_response(feed: ET.Element) -> XMLResponse:
    """Return an XML response with proper OPDS content type."""
    xml = ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    return XMLResponse(
        content=xml,
        media_type="application/atom+xml;profile=opds-catalog;kind=navigation",
    )


def _atom_link(href: str, rel: str = "alternate", type_: str | None = None) -> ET.Element:
    el = ET.Element(f"{{{ATOM_NS}}}link")
    el.set("href", href)
    el.set("rel", rel)
    if type_:
        el.set("type", type_)
    return el


def _author(name: str) -> ET.Element:
    el = ET.Element(f"{{{ATOM_NS}}}author")
    n = ET.SubElement(el, f"{{{ATOM_NS}}}name")
    n.text = name
    return el


@router.get("")
@router.get("/")
async def root(request: Request) -> XMLResponse:
    """OPDS root catalog (navigation feed)."""
    settings = get_settings()
    base = str(request.base_url).rstrip("/")
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    title = ET.SubElement(feed, f"{{{ATOM_NS}}}title")
    title.text = "Alejandría"
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    feed.append(_author("Alejandría"))

    # Self link
    feed.append(_atom_link(f"{base}/opds", "self",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))
    # Start link
    feed.append(_atom_link(f"{base}/opds", "start",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))
    # Up link to itself
    feed.append(_atom_link(f"{base}/opds", "up",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))

    # Navigation entries
    nav_items = [
        ("All Books", f"{base}/opds/books", "navigation", "List all books in the library"),
        ("Recent", f"{base}/opds/recent", "navigation", "Recently added books"),
        ("Authors", f"{base}/opds/authors", "navigation", "Browse by author"),
        ("Series", f"{base}/opds/series", "navigation", "Browse by series"),
        ("Tags", f"{base}/opds/tags", "navigation", "Browse by tag"),
    ]
    for name, href, type_, desc in nav_items:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = name
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = href
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
        content = ET.SubElement(entry, f"{{{ATOM_NS}}}content")
        content.set("type", "text")
        content.text = desc
        link_type = (
            "application/atom+xml;profile=opds-catalog;kind=navigation"
            if type_ == "navigation"
            else "application/atom+xml;profile=opds-catalog;kind=acquisition"
        )
        entry.append(_atom_link(href, "subsection", link_type))

    return _feed_response(feed)


@router.get("/books")
async def books_feed(
    request: Request,
    page: int = 1,
    page_size: int = 50,
) -> XMLResponse:
    """Acquisition feed: all books."""
    calibre = get_calibre_db()
    settings = get_settings()
    base = str(request.base_url).rstrip("/")
    items, total = calibre.list_books(page=page, page_size=page_size)
    return _book_feed(items, base, title="All Books", total=total,
                       page=page, page_size=page_size)


@router.get("/books/{book_id}")
async def book_detail(book_id: int, request: Request) -> XMLResponse:
    """Acquisition entry for a single book (with all formats)."""
    calibre = get_calibre_db()
    book = calibre.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    base = str(request.base_url).rstrip("/")
    summary = calibre._to_summary(book)  # noqa: SLF001

    feed = ET.Element(f"{{{ATOM_NS}}}entry")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = summary.title
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds/books/{book_id}"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    if summary.pubdate:
        ET.SubElement(feed, f"{{{ATOM_NS}}}published").text = summary.pubdate.isoformat()

    for a in summary.authors:
        feed.append(_author(a.name))

    # Acquisition links for each format
    for f in summary.formats:
        mime = _fmt_to_mime(f.fmt)
        link = ET.SubElement(feed, f"{{{ATOM_NS}}}link")
        link.set("rel", "http://opds-spec.org/acquisition")
        link.set("href", f"{base}/api/reader/{book_id}/download?fmt={f.fmt}")
        link.set("type", mime)
        link.set("title", f"Download {f.fmt}")

    xml = ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    return XMLResponse(
        content=xml,
        media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
    )


@router.get("/recent")
async def recent_feed(request: Request) -> XMLResponse:
    """Acquisition feed: recently added books."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    items, total = calibre.list_books(page_size=50, sort="timestamp", order="desc")
    return _book_feed(items, base, title="Recent", total=total, page=1, page_size=50)


@router.get("/authors")
async def authors_feed(request: Request) -> XMLResponse:
    """Navigation feed: all authors."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    authors = calibre.list_authors()

    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = "Authors"
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds/authors"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    feed.append(_author("Alejandría"))
    feed.append(_atom_link(f"{base}/opds/authors", "self",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))
    feed.append(_atom_link(f"{base}/opds", "up",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))

    for a in authors:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = a.name
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = f"{base}/opds/authors/{a.id}"
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
        entry.append(_atom_link(
            f"{base}/opds/authors/{a.id}",
            "subsection",
            "application/atom+xml;profile=opds-catalog;kind=acquisition",
        ))

    return _feed_response(feed)


@router.get("/authors/{author_id}")
async def author_books(author_id: int, request: Request) -> XMLResponse:
    """Acquisition feed: books by author."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    items, total = calibre.list_books(author_id=author_id, page_size=1000)
    return _book_feed(items, base, title=f"Author: {items[0].authors[0].name if items and items[0].authors else 'Unknown'}",
                       total=total, page=1, page_size=1000)


@router.get("/series")
async def series_feed(request: Request) -> XMLResponse:
    """Navigation feed: all series."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    series = calibre.list_series()

    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = "Series"
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds/series"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    feed.append(_author("Alejandría"))
    feed.append(_atom_link(f"{base}/opds/series", "self",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))
    feed.append(_atom_link(f"{base}/opds", "up",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))

    for s in series:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = s.name
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = f"{base}/opds/series/{s.id}"
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
        entry.append(_atom_link(
            f"{base}/opds/series/{s.id}",
            "subsection",
            "application/atom+xml;profile=opds-catalog;kind=acquisition",
        ))

    return _feed_response(feed)


@router.get("/series/{series_id}")
async def series_books(series_id: int, request: Request) -> XMLResponse:
    """Acquisition feed: books in series."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    items = calibre.get_books_in_series(series_id)
    return _book_feed(items, base, title="Series",
                       total=len(items), page=1, page_size=len(items) or 1)


@router.get("/tags")
async def tags_feed(request: Request) -> XMLResponse:
    """Navigation feed: all tags."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    tags = calibre.list_tags()

    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = "Tags"
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds/tags"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    feed.append(_author("Alejandría"))
    feed.append(_atom_link(f"{base}/opds/tags", "self",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))
    feed.append(_atom_link(f"{base}/opds", "up",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))

    for t in tags:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = t.name
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = f"{base}/opds/tags/{t.id}"
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
        entry.append(_atom_link(
            f"{base}/opds/tags/{t.id}",
            "subsection",
            "application/atom+xml;profile=opds-catalog;kind=acquisition",
        ))
    return _feed_response(feed)


@router.get("/tags/{tag_id}")
async def tag_books(tag_id: int, request: Request) -> XMLResponse:
    """Acquisition feed: books with tag."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    items, total = calibre.list_books(tag_id=tag_id, page_size=1000)
    return _book_feed(items, base, title="Tag",
                       total=total, page=1, page_size=1000)


@router.get("/search")
async def opds_search(
    request: Request,
    q: str | None = None,
    page: int = 1,
) -> XMLResponse:
    """OpenSearch endpoint."""
    calibre = get_calibre_db()
    base = str(request.base_url).rstrip("/")
    if not q:
        # Empty search: return OpenSearch description
        opds_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>Alejandría</ShortName>
  <Description>Search books in Alejandría</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <Url type="application/atom+xml;profile=opds-catalog;kind=acquisition"
       template="{base}/opds/search?q={{searchTerms}}&amp;page={{startPage?}}"/>
</OpenSearchDescription>'''
        return XMLResponse(content=opds_xml, media_type="application/opensearchdescription+xml")

    items, total = calibre.list_books(search=q, page=page, page_size=50)
    return _book_feed(items, base, title=f"Search: {q}", total=total, page=page, page_size=50)


# Helpers ------------------------------------------------------------------------

def _book_feed(items, base: str, *, title: str, total: int, page: int, page_size: int) -> XMLResponse:
    """Build an acquisition feed from a list of BookSummary."""
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = title
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = f"{base}/opds"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    ET.SubElement(feed, f"{{{ATOM_NS}}}totalResults").text = str(total)
    ET.SubElement(feed, f"{{{ATOM_NS}}}itemsPerPage").text = str(page_size)
    feed.append(_author("Alejandría"))
    feed.append(_atom_link(f"{base}/opds", "self",
                           "application/atom+xml;profile=opds-catalog;kind=acquisition"))
    feed.append(_atom_link(f"{base}/opds", "up",
                           "application/atom+xml;profile=opds-catalog;kind=navigation"))

    for book in items:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = book.title
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = f"{base}/opds/books/{book.id}"
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
        if book.pubdate:
            ET.SubElement(entry, f"{{{ATOM_NS}}}published").text = book.pubdate.isoformat()
        for a in book.authors:
            feed_a = ET.SubElement(entry, f"{{{ATOM_NS}}}author")
            ET.SubElement(feed_a, f"{{{ATOM_NS}}}name").text = a.name
        # Acquisition link — use EPUB if available, else first format
        preferred = next((f for f in book.formats if f.fmt.upper() == "EPUB"), None)
        if preferred is None and book.formats:
            preferred = book.formats[0]
        if preferred is not None:
            mime = _fmt_to_mime(preferred.fmt)
            link = ET.SubElement(entry, f"{{{ATOM_NS}}}link")
            link.set("rel", "http://opds-spec.org/acquisition")
            link.set("href", f"{base}/api/reader/{book.id}/download?fmt={preferred.fmt}")
            link.set("type", mime)
        # Alternate link to book detail
        alt = ET.SubElement(entry, f"{{{ATOM_NS}}}link")
        alt.set("rel", "alternate")
        alt.set("href", f"{base}/opds/books/{book.id}")
        alt.set("type", "application/atom+xml;profile=opds-catalog;kind=acquisition")

    xml = ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    return XMLResponse(
        content=xml,
        media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
    )


def _fmt_to_mime(fmt: str) -> str:
    return {
        "EPUB": "application/epub+zip",
        "PDF": "application/pdf",
        "MOBI": "application/x-mobipocket-ebook",
        "AZW3": "application/vnd.amazon.ebook",
        "FB2": "application/x-fictionbook+xml",
        "DJVU": "image/vnd.djvu",
        "TXT": "text/plain",
        "HTML": "text/html",
        "RTF": "application/rtf",
        "CBZ": "application/vnd.comicbook+zip",
        "CBR": "application/vnd.comicbook-rar",
    }.get(fmt.upper(), "application/octet-stream")
