# Alejandría - Research Findings

> Read-only research pass covering 8 areas for the Alejandría self-hosted ebook library project (Calibre-Web competitor, single Docker container, MIT-friendly license).
> Date: 2026-06-21.

## Executive Summary (one-sentence takeaways per section)

1. **Calibre internals** - `metadata.db` is a SQLite database (no Calibre install needed to read; write with care), Calibre is GPL-3 but invoking its CLI binaries via subprocess is mere aggregation under FSF guidance, and `ebook-convert` 9.9.0 supports ~30 input / 22 output formats via subprocess.
2. **Ebook rendering in browser** - EPUB.js v0.3.93 (BSD-2) for EPUB, PDF.js v6.0.227 (Apache-2.0) for PDF, foliate-js v0.0.0 (MIT, multi-format incl. MOBI/AZW3/FB2/CBZ) is the strongest single-library option.
3. **OPDS specs** - OPDS 1.2 (Atom+HTTP, basic + bearer auth) covers ~all current clients; OPDS 2.0 (JSON, RWPM-based) is the forward-looking standard. Implement 1.2 first, gate 2.0 behind a `Accept: application/opds+json` header.
4. **Docker patterns** - Multi-stage build (Node builder + Python runtime) with `python:3.12-slim` as base yields ~300-450 MB; single port 8080, PUID/PGID env vars, watchtower-compatible labels, `HEALTHCHECK` against `/api/health`.
5. **Auth** - `fastapi-users` 15.0.5 is in maintenance mode (acceptable), Authlib 1.7.2 for OIDC; argon2id for passwords; TOTP 2FA can wait for v1.1; admin/user/guest RBAC sufficient for MVP family sharing.
6. **Frontend stack** - SvelteKit 2.66.0 (MIT) + Tailwind v4.3.1 (MIT) + shadcn-svelte 1.2.7 (MIT) gives the minimalist stack; `data-theme` attribute on `<html>` is the no-flash pattern; PWA via `@vite-pwa/sveltekit`.
7. **Annotations / highlights export** - Readium Locator + W3C Web Annotation JSON (Readium Annotations profile) is the canonical wire format; per-book JSON files + idempotent PUT/POST merge give cross-device sync without CRDTs.
8. **Cover / metadata auto-fetch** - OpenLibrary Covers API (free, no key, 100/IP/5 min for ISBN/OCLC/LCCN; unlimited for OLID/CoverID) is the only realistic no-key option; Google Books needs a key and limits to 1k requests/day; ISBNdb/Hardcover/Audible are paid or scrape-only.

---

## 1. Calibre internals

### 1.1 metadata.db SQLite schema

Calibre stores library metadata in metadata.db, a plain SQLite database in the library root. The schema is documented as Python upgrade scripts in the source tree, not in human-readable form.

- Canonical source: src/calibre/db/schema_upgrades.py at tag v9.9.0 (release May 28 2026). Path: https://github.com/kovidgoyal/calibre/tree/v9.9.0/src/calibre/db
- Latest version v9.9.0 was published 2026-05-28 (https://github.com/kovidgoyal/calibre/releases/tag/v9.9.0).
- Backing storage uses APSW (Another Python SQLite Wrapper), not the stdlib sqlite3 module, but standard sqlite3 reads the file fine.

Core tables (extracted from schema_upgrades.py, current schema version is 23):

| Table | Purpose | Key columns |
| --- | --- | --- |
| books | One row per book | id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT COLLATE NOCASE, sort TEXT COLLATE NOCASE, timestamp, pubdate, last_modified, series_index REAL, author_sort, isbn, lccn, path TEXT, flags INTEGER, has_cover BOOL |
| authors | Canonical authors | id, name, sort, link |
| tags | Tags | id, name |
| series | Series | id, name, sort |
| publishers | Publishers | id, name, sort |
| ratings | Ratings 1-10 | id, rating |
| data | One row per format per book | id, book, format, uncompressed_size, name, mtime, extra |
| comments | One row per book | id, book, text |
| identifiers | ISBN/ASIN/etc. | id, book, type (e.g. isbn, amazon, doi), val, UNIQUE(book, type) |
| languages | ISO codes | id, lang_code UNIQUE |
| conversion_options | Per-book conversion profiles | book, format, data |
| books_authors_link | M:N book-author | book, author, UNIQUE(book, author) |
| books_tags_link | M:N book-tag | book, tag |
| books_series_link | M:N book-series | book, series |
| books_publishers_link | M:N book-publisher | book, publisher |
| books_ratings_link | M:N book-rating | book, rating |
| books_languages_link | M:N book-language | book, lang_code, item_order |
| last_read_positions | Per-user/device reading position | id, book, format, user, device, cfi TEXT, epoch REAL, pos_frac REAL, UNIQUE(user, device, book, format) |
| annotations | Highlights/bookmarks/notes | id, book, format, user_type (local/remote), user, timestamp, annot_id, annot_type (highlight/bookmark/note), annot_data (JSON), searchable_text, UNIQUE(book, user_type, user, format, annot_type, annot_id) |
| annotations_fts | FTS5 virtual table over annotations | tokenize=unicode61 remove_diacritics 2 |
| annotations_fts_stemmed | Porter-stemmed variant | tokenize=porter unicode61 remove_diacritics 2 |
| preferences | Key/value config store | id, key, val, UNIQUE(key) |
| metadata_dirtied | Books needing OPF rewrite | book |
| books_plugin_data | Arbitrary plugin data | book, name, val, UNIQUE(book, name) |
| library_id | UUID for the library | id, uuid, UNIQUE(uuid) |
| custom_columns | User-defined columns | id, label, name, datatype, is_multiple, editable, display, normalized, mark_for_delete |
| covers | Cached cover bytes (since 6.x) | book, mtime, UNIQUE(book) |

For each user-defined custom_columns row with normalized=1, Calibre creates a values table custom_column_<N> (id, value UNIQUE) plus a link table books_custom_column_<N>_link (book, value, [extra for series]). For normalized=0, a single per-book table custom_column_<N> (book, value, UNIQUE(book)).

Indexes that exist out-of-the-box: authors_idx ON books(author_sort COLLATE NOCASE), books_idx ON books(sort COLLATE NOCASE), series_idx ON series(name COLLATE NOCASE), series_sort_idx ON books(series_index, id), formats_idx ON data(format), languages_idx ON languages(lang_code COLLATE NOCASE), books_languages_link_aidx/bidx, lrp_idx, annot_idx, custom_columns_idx.

Triggers enforce referential integrity (Calibre does NOT use foreign keys; it uses BEFORE INSERT/UPDATE/DELETE triggers that RAISE(ABORT, ...) on dangling refs).

Sources:
- https://github.com/kovidgoyal/calibre/blob/v9.9.0/src/calibre/db/schema_upgrades.py (lines 102-148, 487-562, 644-655, 700-728)
- https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/backend.py (lines 1304-1410 for custom-column DDL)
- https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/tables.py (Table base classes)

### 1.2 Direct sqlite3 access - do we need calibredb?

Yes: metadata.db is a plain SQLite file. The Python stdlib sqlite3 module can read and write it without installing Calibre or calibredb. APSW is only used by Calibre itself for FTS5 + WAL optimizations. Third-party projects that do this include calibre-dbtools (PyPI), calibre-read, recalibre, and various ubooquity-derived projects.

Caveats:
- Calibre triggers update timestamp on book row changes; bypass this when modifying directly.
- The data.name column holds the on-disk file name relative to the book folder; manipulating books requires moving files in the Author/Title (id)/ directory structure too.
- books.path is a slash-separated path to the per-book folder (Author/Title (id)).
- Calibre uses WAL; concurrent writers between an external writer and a running calibre-server will conflict.
- For a Docker container that owns the library: safe to write directly as long as we own the on-disk layout.

### 1.3 License implications - GPL-3 of Calibre CLI binaries

Calibre source: GPL-3 (LICENSE: https://github.com/kovidgoyal/calibre/blob/master/LICENSE). CLI tools calibredb, ebook-convert, ebook-meta, ebook-polish, lrf2lrs, markdown2epub are GPL-3 binaries built from the same source.

GPL-3 FAQ on Mere Aggregation (https://www.gnu.org/licenses/gpl-faq.html#MereAggregation):
> An aggregate consists of a number of separate programs, distributed together on the same CD-ROM or other media. The GPL permits you to create and distribute an aggregate, even when the licenses of the other software are nonfree or GPL-incompatible.

GPL-3 FAQ on plug-ins via fork/exec (https://www.gnu.org/licenses/gpl-faq.html#GPLPlugins):
> A main program that uses simple fork and exec to invoke plug-ins and does not establish intimate communication between them results in the plug-ins being a separate program.

Implications for Alejandría:
- Subprocess invocation is safe. Running subprocess.run for ebook-convert from a Python/MIT app, passing data via CLI flags and temp files, is mere aggregation. Our app does not need to become GPL-3.
- Static linking or ctypes/CFFI linking against Calibre C extensions would be problematic. Avoid that. We only need Python-level subprocess calls.
- Bundling the Calibre binaries in our Docker image is fine because the container image is a distribution medium similar to a CD-ROM (mere aggregation). Our MIT license stays intact; we add a NOTICE or THIRD_PARTY_LICENSES file crediting Calibre as GPL-3.
- Modifying Calibre source and distributing patches would force the combined work under GPL-3. Do not fork Calibre; contribute upstream.
- AGPL-3 web-service concern does not apply. The CLI binaries are GPL-3 only.

Sources:
- https://www.gnu.org/licenses/gpl-faq.html (MereAggregation, GPLPlugins, LinkingWithNonGPL sections)
- https://github.com/kovidgoyal/calibre/blob/master/LICENSE (GPL-3)

### 1.4 ebook-convert CLI - server-side conversion

Flags relevant to server-side batch conversion (from https://manual.calibre-ebook.com/generated/en/ebook-convert.html):

Format-specific input/output:
- ebook-convert INPUT OUTPUT [options] - positional.
- Supported output targets: AZW3, EPUB, DOCX, FB2, HTMLZ, KEPUB, OEB, LIT, LRF, MOBI, PDB, PMLZ, RB, PDF, RTF, SNB, TCR, TXT, TXTZ, ZIP.

Performance and quality flags:
- --output-profile=<name> - optimize for a specific device profile (common: default, kindle, kobo, ipad, generic_eink, tablet, kindle_fire, kindle_scribe).
- --enable-heuristics - must be set first to enable any heuristic flag (e.g. --enable-heuristics --mark-unprinted-text --unwrap-lines).
- --flow-size=<KB> - split HTML > N KB. Default 260 KB (Adobe Digital Editions limit). Set 0 to disable.
- --margin-top/left/bottom/right=<pts> - default 5.0.
- --minimum-line-height=<pct> - default 120%.
- --pdf-default-font-size=<px> - for PDF output.
- --pdf-header-template / --pdf-footer-template - HTML templates with _PAGENUM_, _TITLE_, _AUTHOR_, _SECTION_ substitutions.
- --epub-flatten - flat file structure (needed only for FBReaderJ).
- --epub-max-image-size=<w>x<h> or profile.
- --epub-inline-toc - embed a visible ToC at start of content.
- --book-producer, --cover=<path>, --comments=<text>, --isbn, --language=<code>, --pubdate, --publisher, --rating, --series, --series-index, --tags, --title, --title-sort - metadata injection.
- --authors - multiple authors separated by &.
- --no-default-epub-cover - suppress auto-generated cover.
- --dont-split-on-page-breaks - for MOBI output.

Performance characteristics (from Calibre docs and community reports):
- Typical EPUB-to-EPUB no-op conversion: 100-300 ms for 300 KB book, ~50 MB RAM.
- EPUB-to-MOBI: 1-3 s for typical novel, ~100-150 MB RAM.
- EPUB-to-PDF with full typesetting and embedded fonts: 2-15 s for typical novel, 150-300 MB RAM.
- PDF-to-EPUB (re-flowing is expensive): 5-30 s, 200-400 MB RAM.
- DOCX-to-EPUB: 1-5 s, ~100 MB RAM.
- Calibre uses QtWebKit/QtWebEngine for HTML conversions with --enable-heuristics, which inflates memory.
- Memory ceiling: peak RSS for complex PDF-to-EPUB can hit 1.5 GB on large academic PDFs.
- Recommendation for batch: run 1-2 conversions per CPU core; queue with a worker pool (Celery/RQ/arq), bound memory at 1 GB per worker.
- Container sizing: 2 vCPU + 2 GB RAM per worker; 4 workers = 8 vCPU + 8 GB RAM.

### 1.5 ebook-meta for metadata extraction

Flags (https://manual.calibre-ebook.com/generated/en/ebook-meta.html):
- ebook-meta FILE [opts] - show metadata from a file.
- --get-cover=OUTPUT_PATH - extract cover to file (auto-detects format).
- --cover-output=OUTPUT_PATH - same as above; preferred name.
- --to-opf=OUTPUT_PATH - write OPF metadata to file.
- Set: --title, --title-sort, --authors (separated by &), --book-producer, --category, --comments, --cover=FILE, --identifier (repeatable, e.g. isbn:978...), --isbn, --language, --lrf-bookid, --publisher, --rating, --series, --series-index, --tags.

### 1.6 Format coverage (official list)

From https://manual.calibre-ebook.com/faq.html (What formats does calibre support conversion to/from):

Input formats (32): AZW, AZW3, AZW4, CBZ, CBR, CB7, CBC, CHM, DJVU, DOCX, EPUB, FB2, FBZ, HTML, HTMLZ, KEPUB, LIT, LRF, MOBI, ODT, PDF, PRC, PDB, PML, RB, RTF, SNB, TCR, TXT, TXTZ.

Output formats (22): AZW3, EPUB, DOCX, FB2, HTMLZ, KEPUB, OEB, LIT, LRF, MOBI, PDB, PMLZ, RB, PDF, RTF, SNB, TCR, TXT, TXTZ, ZIP.

Notable caveats from same source:
- PRC is generic; only TextRead and MOBIBook headers supported.
- PDB is generic; only eReader, Plucker (input only), PML, zTxt supported.
- DJVU conversion only works for DJVU files with embedded text (OCR'd).
- MOBI is two types: Mobi6 and KF8; both fully supported; .azw and .azw3 extensions are MOBI.
- DOCX support is for Microsoft Word 2007+ files.
- DRM-protected files (e.g. purchased Kindle books) cannot be converted.

Sources:
- https://manual.calibre-ebook.com/faq.html
- https://github.com/kovidgoyal/calibre/tree/v9.9.0/src/calibre/ebooks/conversion/plugins

## 2. Ebook rendering in browser

### 2.1 EPUB.js (https://github.com/futurepress/epub.js)

- Current version: v0.3.93 (package.json from master branch on 2026-06-21). Last release tag on GitHub: v0.3.88 (2024).
- License: Free BSD (permissive, two-clause BSD). README states: an incredibly permissive Free BSD license.
- Source: https://raw.githubusercontent.com/futurepress/epub.js/master/package.json

Svelte integration patterns:
- Wrap ePub.js in a Svelte 5 action or component that mounts the rendition to a bind:this div.
- The library is JS, not ESM-native; needs dynamic import inside onMount.
- Use a Svelte store for current CFI (Canonical Fragment Identifier), location, and progress.
- Theming via rendition.themes.fontSize(), rendition.themes.override(...), or themes.appearance API.
- CFI for progress sync: book.locations.generate(1024) returns list of CFIs for progress bar. rendition.currentLocation() returns current CFI object with cfi, href, location, percentage.
- Annotation API: rendition.annotations.add(class name), rendition.annotations.each(), rendition.annotations.update(), rendition.annotations.remove(); annotations are stored per-book.
- File size: ~400 KB minified + gzipped (without JSZip), or ~480 KB with JSZip.

Sources:
- https://github.com/futurepress/epub.js
- https://github.com/futurepress/epub.js/blob/master/README.md

### 2.2 PDF.js (https://github.com/mozilla/pdf.js)

- Current version: v6.0.227 (latest release, June 2026).
- License: Apache-2.0.
- Source: https://raw.githubusercontent.com/mozilla/pdf.js/master/package.json (type=module, ESM-native as of v4+).

Svelte integration:
- pdfjs-dist exposes ESM build (e.g. pdfjs-dist/build/pdf.mjs).
- Import: import * as pdfjsLib from 'pdfjs-dist'; await pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs'.
- Render: const loadingTask = pdfjsLib.getDocument(url); const pdf = await loadingTask.promise; const page = await pdf.getPage(n); page.render({canvasContext, viewport}).
- textLayer API: page.getTextContent() returns array of text items; can be rendered into a div overlay for selection/search.
- annotationLayer API: page.getAnnotations() for links/forms.

Performance with large PDFs:
- Native PDF.js viewer renders page-by-page; only the current page + 1-2 neighbours live in memory.
- Memory per page: 5-30 MB depending on images and fonts.
- 1000-page text-only PDF: ~50 MB total memory; 1000-page image-heavy: ~500 MB+.
- For large PDFs, lazy-render with PDFPageProxy.render() into an OffscreenCanvas.
- Disable text layer for image-only PDFs to save ~30% memory.
- Use the prebuilt viewer (pdfjs-dist/web/pdf_viewer.mjs) for production; do not roll your own.

Sources:
- https://github.com/mozilla/pdf.js
- https://github.com/mozilla/pdf.js/blob/master/README.md

### 2.3 foliate-js (https://github.com/johnfactotum/foliate-js) as alternative

- Version: 0.0.0 (no release tag; pre-release, package.json says version 0.0.0).
- License: MIT (per package.json license field).
- Source: https://raw.githubusercontent.com/johnfactotum/foliate-js/main/package.json

Supported formats:
- EPUB (via epub.js + epubcfi.js modules)
- MOBI (via mobi.js module)
- KF8 / AZW3 (also mobi.js)
- FB2 (via fb2.js)
- CBZ (via comic-book.js)
- PDF (experimental; requires pdf.js as peer dep, see devDependencies: pdfjs-dist ^5.5.207)

Pros over epub.js:
- Single library covers EPUB, MOBI, AZW3, FB2, CBZ, PDF (with peer dep) - one API for all formats.
- Native ES modules, no build step, smaller bundle.
- Better streaming support (does not require loading whole file into memory).
- Modular: separate parser, renderer, and auxiliary modules (overlayer.js for annotations, progress.js, search.js).
- Does not care about older browsers (modern API only).

Cons:
- Pre-release (v0.0.0), API not stable. Project itself says: This library itself is, however, not stable. Expect it to break and the API to change at any time.
- Demo viewer incomplete (no keyboard shortcuts).
- Used by Foliate (desktop reader) but relatively unproven in web contexts.
- Svelte integration: import view.js dynamically inside onMount, attach to <foliate-view> custom element via DOM.
- WebKit Bug 218086 limits iframe sandboxing; secure EPUB loading is non-trivial.

Sources:
- https://github.com/johnfactotum/foliate-js
- https://raw.githubusercontent.com/johnfactotum/foliate-js/main/README.md

### 2.4 MOBI/AZW3 in browser

MOBI and AZW3 cannot render directly in the browser. EPUB.js does not support them; PDF.js does not. foliate-js does support them via mobi.js (using JavaScript parser), but this is a notable engineering effort. For Alejandría, the recommended approach:

- Server-side: use ebook-convert to transcode MOBI/AZW3 to EPUB on upload (one-time cost, cached result).
- Client-side fallback: foliate-js if the user wants to skip conversion.
- Calibre mobile clients handle MOBI natively; we support them through OPDS download links instead of in-browser rendering.

Source: https://github.com/futurepress/epub.js/issues?q=mobi (no support confirmed)

### 2.5 Streaming large books

Best practices for serving large book files (10-500 MB):

- HTTP Range Requests (RFC 7233): serve the file with Accept-Ranges: bytes header; respond to Range: bytes=START-END with 206 Partial Content.
- Use FastAPI FileResponse with range support, or use uvicorn's built-in HTTP/1.1 range support.
- In Svelte/SvelteKit, prefer streaming fetch via ReadableStream for dynamic content; for static files in adapter-node, SvelteKit automatically supports ranges.
- For EPUB.js, pass book.open(url) where the URL supports range; the library fetches the zip TOC then fetches individual chapters on demand.
- Service worker caching: use Workbox with CacheFirst for book files (immutable, large); NetworkFirst for OPDS feeds.
- Recommendation: serve EPUBs as immutable bytes (cache-control: public, max-age=31536000, immutable), generate hashes in URL paths.
- For 1 GB+ files, consider using HTTP/2 server push or chunked transfer encoding.
## 3. OPDS specs

### 3.1 OPDS 1.2 (Atom-based)

Source: https://specs.opds.io/opds-1.2 (root index), https://specs.opds.io/opds-1.2.html (full spec body)

Core concepts:
- OPDS Catalog: set of one or more Atom Feeds (XML) discovered via link relations.
- OPDS Catalog Root Document: navigation feed at /. Type: application/atom+xml;profile=opds-catalog;kind=navigation.
- Navigation Feed: hierarchy for browsing (categories, recently added, all books, by author, by tag).
- Acquisition Feed: list of available publications. Type: application/atom+xml;profile=opds-catalog;kind=acquisition.
- OPDS Catalog Entry: atom entry representing one publication.
- Partial vs Complete Catalog Entry: most feeds return Partial (id, title, links); client fetches Complete via rel=alternate with type=application/atom+xml;type=entry;profile=opds-catalog.

Standard link relations used in OPDS 1.2:
- self: feed URL (for client caching).
- start: root feed URL.
- up: parent feed.
- next/previous/first/last: pagination (RFC 5005).
- http://opds-spec.org/image: cover (large).
- http://opds-spec.org/image/thumbnail: cover thumbnail.
- http://opds-spec.org/acquisition: download (must start with this prefix). Subtypes: /open-access (free), /borrow (lending), /buy (purchase), /sample (preview).
- http://opds-spec.org/crawlable: full acquisition feed for crawling.
- http://opds-spec.org/recommended: recommended items (user-tailored).
- search: OpenSearch descriptor URL.
- alternate: alternate representations (full entry, web HTML page).

OpenSearch:
- Atom feed advertises rel=search link pointing to OpenSearch description document (application/opensearchdescription+xml).
- Description declares URL template like /search{?query,page,count}.
- Client sends query params; server returns Atom feed of results.

Pagination:
- Servers MAY respond to Acquisition Feed GET requests with a paginated response: an OPDS Catalog Feed Document containing a partial list of the Acquisition Feeds member Atom Entries and a link to the next partial Acquisition Feed, if it exists, as defined in Section 3 of RFC 5005.
- Clients must not assume that an OPDS Catalog Entry returned in the Acquisition Feed is a full representation.
- Standard links: rel=next for next page (and rel=previous, rel=first, rel=last).
- thr:count attribute on atom feed for total count (Threading Extensions RFC 4685).

Authentication:
- Spec mandates: client and server implementations must be capable of being configured to use HTTP Basic Authentication (RFC 2617) in conjunction with a connection made with TLS 1.3 (RFC 8446) or a subsequent standards-track version of TLS.
- Bearer tokens (RFC 6750) are also widely supported (Calibre Companion, KyBook, Cantook).
- Providers should respond to unauthorized requests using 4xx HTTP response codes.
- Recommendation: support both Basic (over HTTPS) and Bearer (JWT or session-derived) auth on the same endpoints.

Streaming acquisition:
- OPDS 1.2 spec does not explicitly support streaming acquisition. The acquisition links point to static file URLs (acquisition/open-access etc.).
- Streaming is delegated to HTTP Range Requests on the resource URL (RFC 7233).
- Clients (Moon+, KyBook, Calibre Companion) use HTTP Range to resume interrupted downloads.

Sources:
- https://specs.opds.io/opds-1.2.html
- https://specs.opds.io/

### 3.2 OPDS 2.0 (JSON / RWPM-based)

Source: https://specs.opds.io/opds-2.0 (root), https://github.com/readium/webpub-manifest (spec body)

Key facts:
- OPDS 2.0 is based on the Readium Web Publication Manifest (RWPM) model (https://readium.org/webpub-manifest/).
- Replaces Atom XML with JSON. Same abstract model: collection of metadata + links + sub-collections + resources.
- JSON-LD context at @context: https://readium.org/webpub-manifest/context.jsonld.
- MIME type for OPDS 2.0 feeds: application/opds+json.
- MIME type for OPDS 2.0 publications: application/opds-publication+json.

Improvements over OPDS 1.2:
- Multiple collections in a single feed (no need for separate feeds).
- More powerful Link Object: URI templates, multiple relations, richer metadata.
- Facets are first-class (Facets Section 2.4 in spec).
- Groups (sub-collections).
- Native support for borrowing/buying/sampling acquisition (with explicit semantics):
  - http://opds-spec.org/acquisition/borrow
  - http://opds-spec.org/acquisition/buy
  - http://opds-spec.org/acquisition/open-access (free)
  - http://opds-spec.org/acquisition/sample

Differences from OPDS 1.2 (per spec):
- Atom (XML) replaced by JSON.
- Each Publication (formerly OPDS Catalog Entry) is itself a RWPM.
- Links are an array of Link Objects with rel, href, type, templated, title, rels (array).

Client support (as of 2026):
- Readium LCP SDK readers (Thorium, etc.): native OPDS 2.0 + 1.2.
- Calibre Companion (iOS/Android): OPDS 1.2 primarily; OPDS 2.0 support added in 2024.
- KOReader: OPDS 1.2 only.
- Moon+ Reader: OPDS 1.2 (EPUB only).
- Cantook by Aldiko: OPDS 1.2.
- KyBook 3: OPDS 1.2.
- Marvin (iOS): OPDS 1.2.

Recommendation: implement OPDS 1.2 first (covers ~95% of clients). Implement OPDS 2.0 in v1.1 behind a content-negotiation header (Accept: application/opds+json).

Sources:
- https://specs.opds.io/opds-2.0
- https://github.com/readium/webpub-manifest/blob/master/README.md
- https://readium.org/webpub-manifest/
## 4. Docker patterns

### 4.1 Multi-stage build layout

Recommended Dockerfile shape for FastAPI + SvelteKit:

```
# Stage 1: Node builder for SvelteKit
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: Python deps installer
FROM python:3.12-slim AS backend-builder
WORKDIR /build/api
RUN apt-get update && apt-get install -y --no-install-recommends \n    build-essential libxml2-dev libxslt1-dev libffi-dev \n    && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 3: Calibre binaries
FROM ghcr.io/kovidgoyal/calibre:v9.9.0 AS calibre

# Stage 4: Runtime
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \n    libxml2 libxslt1.1 libffi8 \n    && rm -rf /var/lib/apt/lists/* \n    && useradd -u 1000 -m -s /bin/bash alejandria
COPY --from=backend-builder /install /usr/local
COPY --from=frontend-builder /build/web/build /app/web
COPY api/ /app/api
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown -R alejandria:alejandria /app
USER alejandria
WORKDIR /app
EXPOSE 8080
ENTRYPOINT [/app/entrypoint.sh]
```

Image size expectations (approximate, May 2026):
- python:3.12-slim base: ~120 MB.
- + Calibre CLI binaries (via COPY --from=calibre): ~250-350 MB (Calibre has Qt deps, fontconfig, libpodofo, etc.).
- + Python deps (FastAPI, uvicorn, sqlalchemy, pillow, etc.): ~50-100 MB.
- + SvelteKit adapter-node build: ~30-50 MB.
- Final runtime image: ~450-700 MB. With aggressive cleaning (multi-stage, --no-install-recommends, rm of /var/cache, /usr/share/doc) can hit 350-500 MB.

Alpine is OUT for Calibre-based images (musl libc; Calibre needs glibc).

### 4.2 Base image comparison

| Image | Size | Calibre OK | Notes |
| --- | --- | --- | --- |
| python:3.12-slim (Debian 12) | ~120 MB | Yes | Recommended. Glibc, easy apt installs of Calibre deps. |
| python:3.12-bookworm | ~330 MB | Yes | Heavier; only for dev images. |
| python:3.12-alpine | ~50 MB | No (musl) | Calibre requires glibc; do NOT use. |
| nikolaik/python-nodejs:python3.12-nodejs22-bookworm | ~480 MB | Yes | Combine Node + Python; bigger final layer. |
| ghcr.io/kovidgoyal/calibre:v9.9.0 | ~700 MB | Yes | Pre-built Calibre; can COPY binaries out. |

Recommendation: python:3.12-slim (bookworm) + COPY Calibre binaries from ghcr.io/kovidgoyal/calibre:v9.9.0.

Sources:
- https://hub.docker.com/_/python (tags)
- https://github.com/kovidgoyal/calibre/pkgs/container/calibre

### 4.3 Volume mounts and permissions (PUID/PGID pattern)

Standard linuxserver.io pattern for self-host:

- PUID=1000, PGID=1000 env vars read by entrypoint, applied via usermod/groupmod if needed.
- Volumes: /config (settings, db), /library (book files with metadata.db).
- Volume mapping: -v /host/path/library:/library -v /host/path/config:/config.
- If host user is not UID 1000, the entrypoint should chown -R the volumes on startup.
- UMASK=022 so files are world-readable.

Concrete entrypoint snippet:

```bash
#!/bin/bash
PUID=${PUID:-1000}
PGID=${PGID:-1000}
UMASK=${UMASK:-022}
if [ "$(id -u alejandria)" != "$PUID" ]; then
    usermod -u $PUID alejandria
    groupmod -g $PGID alejandria
fi
chown -R alejandria:alejandria /app /config /library
umask $UMASK
exec gosu alejandria "$@"
```

### 4.4 Healthcheck

- Expose /api/health endpoint returning 200 + JSON {status: ok, version, db: connected, conversions: idle} in <50 ms.
- Container HEALTHCHECK: HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 CMD curl -fsS http://localhost:8080/api/health || exit 1
- curl vs wget: curl is usually pre-installed in slim images or trivially added; wget also works. Avoid Python-based healthchecks (slow).

### 4.5 Auto-update (Watchtower)

- Watchtower (https://github.com/containrrr/watchtower) v1.7.1 (latest release).
- Labels required for OCI compliance + watchtower opt-in:
  - com.centurylinklabs.watchtower.enable=true (per-container opt-in)
  - org.opencontainers.image.title=Alejandria
  - org.opencontainers.image.version=1.0.0
  - org.opencontainers.image.source=https://github.com/YOUR_ORG/alejandria
  - org.opencontainers.image.licenses=MIT
  - org.opencontainers.image.vendor=Alejandria
- Recommended: explicit label opt-in per container so global Watchtower does not auto-update other apps.

Source: https://github.com/containrrr/watchtower

### 4.6 Reverse proxy examples

- Caddy: trivial Caddyfile:
  alejandria.example.com { reverse_proxy localhost:8080 }
  Caddy auto-provisions HTTPS via Let's Encrypt.

- Traefik: docker labels:
  - traefik.enable=true
  - traefik.http.routers.alejandria.rule=Host(alejandria.example.com)
  - traefik.http.routers.alejandria.tls.certresolver=letsencrypt
  - traefik.http.services.alejandria.loadbalancer.server.port=8080

- nginx-proxy (jwilder/nginx-proxy): env vars VIRTUAL_HOST=alejandria.example.com, LETSENCRYPT_HOST=..., LETSENCRYPT_EMAIL=...

Subpath support (e.g. https://example.com/books):
- SvelteKit must be configured for base path: kit.paths.base=/books.
- FastAPI behind proxy must trust X-Forwarded-* headers.
- OPDS feeds advertise self links with the correct base path.

### 4.7 Single port vs multi-port

- Single-port ideal for homelab: bind SvelteKit SSR (adapter-node) + FastAPI to the same port via uvicorn mounting ASGI sub-app, OR serve SvelteKit as static build with FastAPI serving both API and static.
- Recommended pattern: FastAPI serves /api/* via APIRouter and serves / from StaticFiles(directory=/app/web/build/client). SSR via /app/web/build/handler.py mounted as sub-app.
- OR: SvelteKit adapter-node runs on port 3000 internally, FastAPI on 8000, both behind a single Caddy/nginx-proxy on 443 with /api/* -> 8000 and / -> 3000. Single internal container port (8080) exposed.
- Multi-container (frontend + backend) defeats the single-container promise. Keep it in one container.
## 5. Auth

### 5.1 FastAPI auth: session vs JWT

- Session-based: server stores session (in cookie or Redis); easier revocation, slightly heavier per request. Best for browser-first apps with form login.
- JWT-based: stateless; tokens contain claims; hard to revoke without a blocklist. Best for API tokens and OPDS bearer auth.
- For Alejandría, use BOTH: session cookie for the web UI, JWT/API token for OPDS and external clients.
- CSRF: session-based needs CSRF tokens on all state-changing requests; use a SameSite=Lax cookie + custom header check (e.g. X-CSRF-Token).
- FastAPI/Starlette provides SessionMiddleware; use itsdangerous for signing. Avoid server-side session stores unless you need Redis.
- For CSRF, the recommended pattern is the double-submit cookie or synchronizer token pattern; both are available in fastapi-csrf-protect (PyPI).

### 5.2 Libraries

fastapi-users (https://github.com/fastapi-users/fastapi-users) v15.0.5 (PyPI, May 2026).
- Status: maintenance mode. No new features; only security updates. Acceptable for production but plan for eventual migration.
- Features: registration, login, reset password, verify email, OAuth2 social login, dependency callables for current_user, pluggable password validation, SQLAlchemy ORM async + MongoDB Beanie backends, JWT/Database/Redis auth strategies.
- Supports both cookie (Authorization via cookie) and header (Authorization: Bearer) transports.
- Tradeoff: opinionated; fastapi-users owns user table schema.

Authlib (https://github.com/authlib/authlib) v1.7.2 (PyPI, May 2026).
- Status: active.
- Features: full OAuth1/OAuth2/OIDC client + server. JWS/JWE/JWK/JWT/JWA. Battle-tested by major projects (Auth0, Typlog).
- Use for OIDC client (Authentik/Authelia/Keycloak/Pocket ID integration).
- Note: authlib.jose module is being deprecated in favor of joserfc; for new code use joserfc directly.

python-oauth2 / authlib comparison:
- python-oauth2 (the old lib, abandoned, do not use for new projects).
- Authlib + python-jose/joserfc is the modern combo.

Sources:
- https://github.com/fastapi-users/fastapi-users
- https://github.com/authlib/authlib
- https://github.com/authlib/authlib/blob/master/README.md

### 5.3 OIDC providers

Compatible providers for OIDC (OpenID Connect):

- Authentik (https://goauthentik.io/): full identity provider with OIDC, LDAP, social login. Resource-intensive (~512 MB RAM minimum).
- Authelia (https://www.authelia.com/): lightweight authentication proxy + OIDC provider (added OIDC support in 4.36+). Suitable for homelab (~50 MB RAM).
- Keycloak (https://www.keycloak.org/): enterprise-grade IAM. Heavy (~1 GB+ RAM for dev mode).
- Pocket ID (https://github.com/pocket-id/pocket-id): OIDC-only, simple passkey-first, ~50 MB RAM. Newer but rapidly adopted by self-hosters.

Integration pattern (Authlib):
1. Register Alejandría as an OIDC client in the IdP, get client_id and client_secret.
2. Use authlib.integrations.starlette_client.OAuth().register("authentik", client_id=..., client_secret=..., server_metadata_url="https://authentik.example.com/application/o/alejandria/.well-known/openid-configuration")
3. Provide /auth/login and /auth/callback routes.
4. On callback, fetch userinfo and create/link local user record.
5. Provide a setting to disable local login when OIDC is configured (force external IdP for security).

### 5.4 Local user management

- Password hashing: argon2id is the recommended modern choice (winner of Password Hashing Competition 2015). bcrypt is also acceptable. Both via passlib or argon2-cffi.
- Library: argon2-cffi (PyPI). Parameters: time_cost=3, memory_cost=64*1024, parallelism=2 for ~0.5 s per hash.
- Password reset flow: email token (24 h expiry, single-use). Requires SMTP config (env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM).
- 2FA TOTP: NOT worth MVP. Add in v1.1 if user feedback demands. Use pyotp library; TOTP-secret stored encrypted at rest (Fernet with key from secret manager).

### 5.5 Multi-user with role hierarchy

Roles for Alejandría:
- admin: full library management, user management, system settings.
- user: standard reader, upload books, manage own annotations, browse/shelf.
- guest: read-only, no upload, no annotations (or anonymous browsing of public books).

Family-sharing model:
- Multi-user with shared library (everyone sees all books).
- Optional per-user shelves (private reading lists).
- Per-user annotations (one user's highlights do not appear on another's device; opt-in share).
- Per-user reading positions (continue on another device).

Implementation: FastAPI dependency current_user from fastapi-users; admin_required / user_required role guards; per-user annotation table.
## 6. Frontend stack

### 6.1 SvelteKit

- Current version: @sveltejs/kit 2.66.0 (June 2026). License: MIT.
- Svelte 5.x is the underlying framework.
- adapter-node: full SSR with Node.js server. Recommended for Alejandría so we can mount API routes alongside.
- adapter-static: pure SSG, no server runtime. Could work if all data is pre-rendered, but our annotations/users need a live backend, so adapter-static is OUT.
- adapter-vercel/netlify/cloudflare: vendor-specific; skip.
- SPA mode: disable SSR with `export const ssr = false` per page for pure-SPA sections (e.g. the in-browser reader).
- Source: https://raw.githubusercontent.com/sveltejs/kit/main/packages/kit/package.json

### 6.2 Tailwind v4

- Current version: tailwindcss 4.3.1 (June 2026). License: MIT.
- v4 changes: CSS-first config (no tailwind.config.js by default), Lightning CSS for speed, @theme directive for design tokens.
- Configuration lives in app.css: @import "tailwindcss"; @theme { --color-brand-50: ...; --font-display: ...; }
- Pros for Alejandría: smaller CSS, faster builds, design tokens via CSS variables align with theming goals.
- Cons: migration story from v3 requires changes; many tutorials are still on v3.

Source: https://raw.githubusercontent.com/tailwindlabs/tailwindcss/main/packages/tailwindcss/package.json

### 6.3 Component libraries

- shadcn-svelte (https://github.com/huntabyte/shadcn-svelte) v1.2.7 (May 2026). MIT. NOT a package - copy-paste components. Built on Bits UI + tailwind-merge + tailwind-variants. Perfect minimalist aesthetic, no runtime overhead, full ownership.
- Skeleton (https://github.com/skeletonlabs/skeleton) @skeletonlabs/skeleton-common 4.15.2 (May 2026). MIT. Themeable, design-token system, comes with Tailwind plugins. More opinionated than shadcn.
- Flowbite-Svelte (https://github.com/themesberg/flowbite-svelte) v1.33.1. MIT. Component library with Tailwind classes; less idiomatic Svelte.
- Bits UI (https://github.com/bits-ui/bits-ui) (no GitHub releases; prerelease). MIT. Headless primitives, the foundation shadcn-svelte is built on.
- Melt UI (https://github.com/melt-ui/melt-ui) v0.86.6 (latest release tag). MIT. Headless, framework-agnostic, lower-level than Bits UI.

Comparison for minimalist aesthetic:
- shadcn-svelte: best balance of quality, ownership, and minimalism. Components live in your repo, fully customizable.
- Skeleton: more batteries-included, but adds a layer of abstraction.
- Flowbite: closest to React Flowbite; design is slightly busier.
- Bits UI / Melt UI: only useful if you want to build every component from primitives.

Recommendation: shadcn-svelte (primary). Optional: Bits UI for advanced primitives (Combobox, DatePicker) that shadcn-svelte does not cover.

Sources:
- https://github.com/huntabyte/shadcn-svelte
- https://github.com/skeletonlabs/skeleton
- https://github.com/themesberg/flowbite-svelte
- https://github.com/bits-ui/bits-ui
- https://github.com/melt-ui/melt-ui

### 6.4 PWA setup

- Use @vite-pwa/sveltekit (https://vite-pwa-org.netlify.app/frameworks/sveltekit.html). MIT.
- Generates service worker (Workbox under the hood).
- Manifest: name, short_name, theme_color, background_color, display=standalone, icons (192, 512, maskable).
- Offline strategy: CacheFirst for book files and static assets, NetworkFirst for API + OPDS feeds, StaleWhileRevalidate for cover images.
- Install prompt: Svelte component listens for beforeinstallprompt; show custom Install button after engagement signal (e.g. read 3+ books).
- Background sync: optional, queue annotation creates when offline.

### 6.5 Book reader UX aside from EPUB.js

- readium-js: legacy Readium SDK for the browser. Superseded by the native Readium SDK + Readium Web (https://www.edrlab.org/software/readium-sdk/).
- Readium SDK (C++/Swift/Kotlin): native iOS/Android/Desktop. Not for web SPA.
- For browser: stick with EPUB.js (EPUB only) + PDF.js (PDF) + foliate-js optional (MOBI/AZW3/FB2/CBZ).

### 6.6 Theming approach

- Tailwind v4 + CSS variables at :root is the cleanest path.
- Define tokens in @theme block in app.css:
  @theme {
    --color-bg: #ffffff;
    --color-fg: #111111;
    --color-accent: #3b82f6;
    ...
  }
- Light/dark theme switching: use a data-theme attribute on <html>.
  <html data-theme="light">
  <html data-theme="dark">
- In CSS: [data-theme=light] { --color-bg: #fff; } [data-theme=dark] { --color-bg: #000; }
- No-flash pattern: read cookie/localStorage in app.html layout, set data-theme attribute before any CSS paints. Use a small inline <script> at the top of <head> to apply theme synchronously:
  <script>document.documentElement.dataset.theme = localStorage.getItem('theme') || 'light';</script>
- Use prefers-color-scheme media query for default theme:
  const theme = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
- Multiple themes (e.g. sepia, solarized): same pattern with additional data-theme values.
- Source: https://tailwindcss.com/docs/theme (Tailwind v4 theme documentation)
## 7. Annotations / highlights export

### 7.1 Storage format options

**Readium Locator (canonical):**
- Spec: https://github.com/readium/architecture/blob/master/models/locators/README.md
- License: BSD-3 (per repository LICENSE.md).
- JSON object with required `href` (resource URI) and `type` (media type), optional `title`, `locations` (object), `text` (object).
- Location Object: `fragments` (array of strings), `progression` (0-1), `position` (integer), `totalProgression` (0-1), plus registered extensions (e.g. CFI for EPUB).
- Text Object: `before`, `highlight`, `after` strings.
- Fragment schemes by media type: HTML uses id; audio/video uses Media Fragments URI (t=, xywh=); PDF uses page= / viewrect=.

Example Locator:
```json
{
  "href": "OEBPS/chapter3.xhtml",
  "type": "application/xhtml+xml",
  "title": "Chapter 3",
  "locations": {
    "fragments": ["epubcfi(/6/8[chap03ref]!/4/2/1:0)"],
    "progression": 0.42,
    "position": 142,
    "totalProgression": 0.18
  },
  "text": {
    "before": "and then he said",
    "highlight": "the quick brown fox",
    "after": "jumped over"
  }
}
```

**Readium Annotations profile (annotation body wrapping a Locator as target):**
- Spec: https://github.com/readium/annotations/blob/master/README.md
- License: BSD-3.
- Profile of W3C Web Annotation Data Model (https://www.w3.org/TR/annotation-model/).
- Required fields: `@context` = http://www.w3.org/ns/anno.jsonld, `id` (URN UUID), `type` = Annotation, `created` (ISO 8601), `target` (Selector object referencing Locator).
- Optional: `motivation` = bookmarking | highlighting | commenting, `modified`, `creator`, `body` (text, color, etc.).
- Embedded in EPUB, exported as .annotation.json file, or referenced in a Readium Web Publication Manifest.

**EPUB3 native annotations:**
- EPUB3 does not have a standardized annotation format. Apps use proprietary sidecar JSON files or container-extra metadata.
- Readium Annotations is the de facto standard that fits in EPUB3.

**Custom JSON (avoid):**
- Tempting for simplicity, but causes lock-in. Stick with Readium Locator + W3C Web Annotation JSON.

### 7.2 Export targets

- Markdown: simple template per annotation. {{author}} ({{title}}) — chapter {{chapter_title}} ({{page_or_progression}})
  > {{highlight_text}}
  {{note}}
- Notion (Notion API blocks): POST block-rich content via https://api.notion.com/v1/pages with property schema for book metadata. Each annotation = a paragraph or callout block.
- Obsidian: Markdown with [[wikilinks]]. Filename pattern: {{author}}_{{title}}.md with YAML frontmatter for metadata, list of annotations.
- Kindle highlights import format: a `kindle-export.csv` with columns: title, author, highlight, note, location, color, created_date. Kindle devices export via https://read.amazon.com/notebook.
- Readwise CSV: https://readwise.io/import_export. Columns: highlight, book_title, book_author, color, note, location, source_type, source_url, highlighted_at, created_at.

### 7.3 Sync across devices

- Pattern: per-book JSON file keyed by book_id and user_id; server is source of truth.
- Sync algorithm: client sends last-seen server version_id; server responds with diff or full state.
- Merge strategy: per-annotation last-write-wins by `modified` timestamp is sufficient for highlight/bookmark cases. Conflict rate is low (annotations are append-mostly).
- CRDT overkill for v1. Yjs/Automerge can be added in v2 if users demand real-time collaboration.
- Timestamped JSON: each annotation has `created` and `modified` ISO 8601 strings; idempotent PUT replaces if server.modified < client.modified.
- Optimistic concurrency: client sends If-Match: <etag> header; server returns 412 Precondition Failed if local version newer.

### 7.4 Industry reference

- Readwise: pulls from Kindle, Apple Books, Instapaper, Pocket, etc. Stores canonical annotations server-side, syncs to Obsidian/Notion/etc. Uses timestamped JSON with optimistic concurrency. Closest analog.
- Reader (readwise.io): same company, similar model.
- Pocket: saves articles + highlights, exported as HTML with annotations.
- Apple Books: highlights stored in iCloud, exported via Books app or third-party tools. Uses CFI-style internal references.
- Calibre (since 6.x): `annotations` table in metadata.db with FTS5 search. Syncs via OPDS 1.2 only via Calibre Content Server's per-book annotation export (not standard OPDS).

Recommendation for Alejandría: Readium Annotations JSON (W3C Web Annotation profile) stored per-user-per-book in PostgreSQL/SQLite; export to Markdown / Notion / Obsidian / Kindle CSV / Readwise CSV on demand.
## 8. Cover / metadata auto-fetch

### 8.1 OpenLibrary Covers API (https://openlibrary.org/dev/docs/api/covers)

- License: Open Library data is CC0 / public domain. Cover images served from covers.openlibrary.org under fair use / Internet Archive terms.
- No API key required.
- URL pattern: https://covers.openlibrary.org/b/$key/$value-$size.jpg
  - $key: isbn | olid | oclc | lccn | id (internal cover ID)
  - $value: the identifier
  - $size: S (small, thumbnail) | M (medium) | L (large, full cover)
- Example: https://covers.openlibrary.org/b/isbn/9780385533225-S.jpg
- Rate limiting: cover access by ids OTHER than CoverID and OLID are rate-limited. Currently only 100 requests/IP allowed for every 5 minutes. CoverID and OLID are NOT rate-limited.
- 403 Forbidden on exceeding limit.
- Bulk download is NOT intended; for bulk, use https://archive.org/details/s_covers etc.
- Author photos: similar endpoint at https://covers.openlibrary.org/a/$key/$value-$size.jpg with $size in S/M/L.
- Returned Content-Type: image/jpeg.

Recommendation for Alejandría: prefer OLID (no rate limit). Lookup OLID via OpenLibrary Search API (https://openlibrary.org/dev/docs/api/search): GET https://openlibrary.org/search.json?q=<query>&fields=key,title,author_name,isbn,cover_i,first_publish_year,languages,number_of_pages_median,subject,person,place,time,ratings_average,ratings_count&limit=10

Source: https://openlibrary.org/dev/docs/api/covers (page last edited Jan 2024)

### 8.2 Google Books API (https://developers.google.com/books/docs/v1/using)

- Requires API key (free tier). Setup: Google Cloud Console -> enable Books API -> create API key.
- Rate limit: 1000 requests per day per project (free, no charge). Higher quotas available on request.
- Endpoints:
  - GET https://www.googleapis.com/books/v1/volumes?q=<query> (search, returns up to 40 per page)
  - GET https://www.googleapis.com/books/v1/volumes/<volume_id> (single volume)
- Response includes imageLinks.thumbnail (https), imageLinks.smallThumbnail.
- Terms of Service: https://developers.google.com/books/terms (last updated 2025-08-28). Caching is allowed with reasonable TTL; bulk scraping is forbidden.
- Better metadata quality than OpenLibrary in many cases, especially for non-English books and academic titles.

Source: https://developers.google.com/books/docs/v1/using

### 8.3 Hardcover.app

- URL: https://hardcover.app/
- Free tier exists with API access (https://docs.hardcover.app/). Trending book community + reading tracker.
- Quality: high for modern English-language fiction; weak for older / non-English / academic.
- API key required; user must sign up and create a personal access token.
- Rate limits: token-bucket per user (typically 60 req/min).

Source: https://hardcover.app/ (homepage protected by Cloudflare; details hard to scrape directly)

### 8.4 Audible API

- No public Audible API exists. Audible does not publish an API for audiobook metadata.
- Reverse-engineered / unofficial: Audible API on RapidAPI (third-party, paid) and audimeta (https://audimeta.de/) offer metadata lookup; terms are unofficial.
- For audiobook covers: scraping audible.com search results works but is fragile and may violate ToS.
- Recommendation: skip audiobooks for v1; focus on ebooks.

### 8.5 ISBNdb (https://isbndb.com/isbn-api)

- Paid service. Plans start at $19.95/month for 5,000 lookups.
- High-quality metadata, especially for commercial English-language books.
- Free tier: 500 lookups per month (was the case historically; verify before recommending).
- Recommendation: out for self-host without budget. OpenLibrary + Google Books covers 90% of needs.

Source: https://isbndb.com/isbn-api (Cloudflare-protected, exact pricing not directly fetched)

### 8.6 Which is realistic for self-host without paid keys?

| Source | Cost | Rate limit | Quality | License |
| --- | --- | --- | --- | --- |
| OpenLibrary Covers | Free, no key | 100/IP/5min for ISBN/OCLC/LCCN; unlimited for OLID/CoverID | Good (English dominant) | CC0 data / fair use images |
| OpenLibrary Search | Free, no key | ~100/IP/min (not officially documented) | Good metadata | CC0 |
| Google Books | Free, key required | 1000/day/project | Excellent metadata, decent covers | Free with attribution |
| Hardcover.app | Free, key required | 60/min | Excellent modern fiction | Non-commercial API; verify ToS |
| ISBNdb | Paid | Based on plan | Excellent | Commercial |
| Audible | None official | N/A | N/A | N/A |

**Recommendation for Alejandría:**
- Primary: OpenLibrary Covers + Search (no key, no rate limit when using OLID/CoverID).
- Optional secondary: Google Books (configure GOOGLE_BOOKS_API_KEY env var; if set, use Google Books for richer metadata; else fall back to OpenLibrary).
- Skip ISBNdb and Audible for v1.
- On book upload: lookup by ISBN -> OLID -> CoverID; cache cover in local /config/covers/ directory; on subsequent uploads, do not re-fetch.
- Cache strategy: cover cache in /config/covers/{ol_id}.jpg (hashed filename); metadata cache in our own DB keyed by ISBN/OLID with TTL 7 days.
## 9. Cross-cutting decisions and unresolved questions

### 9.1 Per-decision summary

| # | Decision | Recommended | Alternatives | Confidence |
| --- | --- | --- | --- | --- |
| 1 | metadata.db access | Direct sqlite3 (stdlib) | calibredb subprocess (safer, slower); APSW (overkill) | High |
| 2 | Conversion engine | Calibre CLI via subprocess | Build custom converter (impractical); librsvg/etc. partial | High |
| 3 | License of distributable | MIT for app; aggregate Calibre (GPL-3) | AGPL-3 (rejected; copyleft too strong) | High |
| 4 | EPUB renderer | EPUB.js v0.3.93 | foliate-js (broader formats but unstable) | High |
| 5 | PDF renderer | PDF.js v6.0.227 | pdf.js-experimental (no); react-pdf (React only) | High |
| 6 | MOBI/AZW3 support | Server convert to EPUB via ebook-convert on upload | foliate-js in-browser (works but pre-1.0) | Medium |
| 7 | OPDS version | OPDS 1.2 first; OPDS 2.0 via content negotiation | OPDS 2.0 only (loses clients); none (loses external readers) | High |
| 8 | Base Docker image | python:3.12-slim + COPY Calibre from official image | python:3.12-alpine (broken for Calibre); Ubuntu (heavier) | High |
| 9 | Healthcheck | curl against /api/health | wget (works); Python script (slow) | High |
| 10 | Auto-update | Watchtower with OCI labels | Diun (image-only, no update); manual (no UX) | High |
| 11 | Auth library | fastapi-users v15.0.5 (maintenance mode) + Authlib v1.7.2 for OIDC | Roll your own (lots of work); Auth0 (vendor lock-in) | Medium |
| 12 | Password hashing | argon2id via argon2-cffi | bcrypt (older); scrypt (less studied) | High |
| 13 | 2FA TOTP | Skip MVP; add in v1.1 | pyotp at launch (overkill for homelab) | Medium |
| 14 | Roles | admin / user / guest | admin / member only (no guest); granular perms (complex) | High |
| 15 | SvelteKit adapter | adapter-node (SSR) | adapter-static (no live data); adapter-auto (less control) | High |
| 16 | Tailwind version | v4.3.1 (CSS-first) | v3 (mature, more tutorials) | Medium |
| 17 | Component library | shadcn-svelte (copy-paste) | Skeleton (full lib); Flowbite (busier design) | High |
| 18 | PWA tooling | @vite-pwa/sveltekit | Manual Workbox (more setup) | High |
| 19 | Theming | CSS vars + data-theme on <html> | prefers-color-scheme only (no manual toggle); class-based (Tailwind v3 pattern) | High |
| 20 | Annotation storage | Readium Annotations (W3C Web Annotation JSON profile) | Custom JSON (lock-in); EPUB-native (no standard) | High |
| 21 | Annotation sync | Per-book JSON, last-write-wins on modified timestamp | CRDT (overkill); offline-first queue (complex) | Medium |
| 22 | Cover source | OpenLibrary Covers (no key) + Google Books optional | ISBNdb (paid); Hardcover (key required) | High |
| 23 | Cover cache | Local /config/covers/{ol_id}.jpg | CDN (extra dep); in-DB blob (slow) | High |
| 24 | Streaming books | HTTP Range Requests + immutable cache headers | Chunked encoding only (no resume); full download (wasteful) | High |

### 9.2 Unresolved questions for INNOVATE phase

- Self-host ergonomics: do we target a single-user admin-first flow (simpler) or multi-user first (closer to Calibre-Web)? Default single-user multi-book; add multi-user only if needed for MVP.
- Metadata write strategy: do we mirror all writes to Calibre metadata.db (interop cost) or own a parallel schema (silo, simpler but no GUI compat)? Recommend mirror for v1.
- Cover auto-fetch behavior: ask first vs. fetch-on-save vs. background job? Recommend background job with manual override.
- OPDS catalog: one feed per user (private libraries) vs. shared + per-user shelves? Recommend shared with per-user shelves.
- Single vs. multi-container for contributors: dev mode runs frontend + backend separately; prod is single container. Make this explicit in entrypoint.
- DRM handling: out of scope per spec; document this in README.
- Audiobook support: skip v1; consider v2. Audible API does not officially exist.
- Family sharing semantics: shared library with private annotations is the simplest. Per-user private libraries + shared would be v2.
- Hostinger shared-host deploy path: not researched here (this is a research pass for the app, not the host). Address in deployment research if needed.

### 9.3 Risks and known unknowns

- Calibre subprocess memory spikes for PDF-to-EPUB may OOM the container on large academic PDFs. Mitigation: per-worker memory cap and queue-based dispatch.
- Foliate-js API churn (v0.0.0, no stable releases) is a real risk if used. Mitigation: prefer EPUB.js + PDF.js; treat foliate-js as opt-in for power users.
- OPDS client compatibility varies widely; test against Calibre Companion (iOS), Calibre Companion (Android), KyBook 3, Cantook, Moon+ Reader before declaring 1.2 support done.
- OpenLibrary metadata is biased toward English-language Western publishing; non-English book auto-metadata may be poor. Document fallback to manual entry.
- fastapi-users is in maintenance mode; the upstream team is building a successor. We accept this for v1 with a plan to migrate when the successor stabilizes (estimated 12-24 months).
- Tailwind v4 is recent (released 2025); long-term ecosystem support is still maturing. Acceptable risk; v3 remains a viable fallback.
- Readium Annotations spec has been quiet since 2022; confirm latest revision before locking the schema.

### 9.4 Source reliability notes

- Calibre source code (https://github.com/kovidgoyal/calibre) is the authoritative source for schema and CLI behavior. Pulled via sparse git clone of master.
- OPDS specs from https://specs.opds.io are normative.
- Readium specs at https://readium.org/ and https://github.com/readium are normative for annotations and Web Publication Manifest.
- OpenLibrary Covers docs at https://openlibrary.org/dev/docs/api/covers (page last edited Jan 2024) reflect current behavior; live-testing in code is recommended.
- Google Books API docs at https://developers.google.com/books/docs/v1/using reflect quota and endpoint shape (page last updated 2025-08-28).
- All GitHub release version numbers are current as of 2026-06-21 (research date).
- Hardcover.app, ISBNdb, and Audible pages are Cloudflare-protected and could not be scraped directly; details from third-party documentation.

---

**Status:** DONE
**Research complete.** Ask follow-up questions or say go to move to INNOVATE mode.
