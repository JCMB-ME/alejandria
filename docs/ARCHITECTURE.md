# Alejandría — Architecture

Self-hosted ebook library web app. Single Docker image, multi-user, Calibre-compatible.

## High-level

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (SPA)                            │
│  SvelteKit + Tailwind + EPUB.js + PDF.js                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / REST + JSON / OPDS-XML
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI app                               │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  /api    │  /opds   │  /auth   │  reader  │  covers  │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│                                                              │
│  ┌──────────────────────┐  ┌────────────────────────────┐   │
│  │  App DB (SQLite)     │  │  Calibre DB (SQLite)       │   │
│  │  users, sessions,    │  │  metadata.db               │   │
│  │  progress, highlights│  │  (read-only by us)         │   │
│  │  shelves, annotations│  │                            │   │
│  └──────────────────────┘  └────────────────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │ Library      │  │ Conversion   │  │  SMTP          │    │
│  │ Scanner      │  │ (Calibre CLI)│  │  (send-Kindle) │    │
│  │ (watchdog)   │  │              │  │                │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Backend (Python 3.12 + FastAPI)

- **API layer** (`routers/`): HTTP endpoints, auth, validation
- **Services** (`services/`): business logic
  - `calibre_db.py` — reads Calibre's `metadata.db` directly via `sqlite3` (no Calibre install required for read)
  - `scanner.py` — `watchdog` watches library dir, calls `calibredb add` for new files
  - `cover.py` — extracts covers from EPUB/PDF/MOBI; uses `ebook-meta` (Calibre CLI) as fallback
  - `convert.py` — wraps `ebook-convert` for on-the-fly format conversion
  - `smtp.py` — `aiosmtplib` for Send-to-Kindle
  - `highlights.py`, `stats.py` — domain services
- **Models** (`models/`): SQLAlchemy 2.0 declarative models for app DB
- **Auth** (`auth/`): argon2 + JWT + OIDC client

### Frontend (SvelteKit 2 + Svelte 5)

- **Routes** (`routes/`): page components (Svelte 5 runes)
- **API client** (`lib/api/`): typed wrapper around `fetch`
- **Components** (`lib/components/`): reusable UI primitives
- **Reader**:
  - **EPUB.js** (futurepress/epubjs) — for EPUB files
  - **PDF.js** (Mozilla) — for PDF files
  - Plain `<pre>` for FB2/RTF/TXT after server-side conversion
- **State**: Svelte stores; auth stored in cookies (HttpOnly, SameSite=Lax)

### Docker

Multi-stage build:
1. `node:20-slim` — builds SvelteKit
2. `debian:bookworm-slim` — installs Calibre CLI (linux-installer)
3. `python:3.12-slim` — installs Python deps via `uv`
4. Final `python:3.12-slim` runtime — combines frontend build, Python deps, Calibre CLI

Single port (8080). Single image. Volume mounts for library + config.

## Data flow examples

### Reading a book (EPUB)

1. User clicks "Read" on `/books/{id}`
2. Frontend navigates to `/read/{id}`
3. Reader page fetches `/api/reader/{id}/file?fmt=EPUB` (with auth cookie)
4. Backend: `services/convert.get_readable_file()` checks format
5. If EPUB: serves original file from `/library/Author/Title/Title - id.epub`
6. EPUB.js loads the file in-browser
7. Position changes → PUT `/api/reader/{id}/progress` → `ReadingProgress` row in app DB

### Reading a MOBI book

1. User opens book (only has MOBI format)
2. Reader page fetches `/api/reader/{id}/file`
3. `get_readable_file()` sees MOBI, picks EPUB as target
4. Calls `convert()` which shells out to `ebook-convert source.mobi target.epub`
5. Caches result in `/config/caches/conversions/{id}/book.epub`
6. Returns the converted file
7. Subsequent reads hit the cache

### Adding a book

1. User copies `book.epub` into `/library/Author Name/Book Title (1234)/`
2. `watchdog` event fires
3. `LibraryScanner.add_book()` calls `calibredb add`
4. Calibre updates `metadata.db` with metadata + cover extraction
5. Next `/api/books` request reads the new entry

## Storage

| Path | Purpose | Mounted |
|------|---------|---------|
| `/library` | User's ebook library (Calibre format) | yes |
| `/library/metadata.db` | Calibre's metadata DB | (part of library) |
| `/config/alejandria.db` | App DB (users, progress, etc.) | yes |
| `/config/caches/` | Conversion cache, cover cache | yes |

## Security

- Passwords: argon2 (memory-hard, GPU-resistant)
- Sessions: HttpOnly cookies, JWT with HS256, server-side session table for revocation
- CSRF: separate cookie for double-submit pattern
- PUID/PGID: homelab-friendly permission mapping
- No secret in URL params; tokens never in localStorage

## License

MIT for the core. Optional Calibre CLI integration is GPL-3.0 — only the Calibre binary falls under GPL, our code remains MIT. See [LICENSE](../LICENSE).
