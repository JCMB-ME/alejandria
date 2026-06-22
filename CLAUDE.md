# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Alejandría** — self-hosted ebook library web app. Single Docker image, multi-user, Calibre-compatible. Modern, minimalist alternative to Calibre-Web. Python 3.12 + FastAPI backend, SvelteKit 2 + Svelte 5 frontend, packaged with Calibre CLI in one container on port 8080.

User-facing intent: `library/` is the user's Calibre library (mounted volume). `config/` is the app's runtime data (SQLite, caches). The Calibre binary runs inside the container; the app talks to it via `calibredb`/`ebook-convert` for add/convert/cover extraction.

## Global orchestration harness

This project follows the RIPER-5 spec-driven workflow defined in `~/.claude/CLAUDE.md`. Operate as orchestrator: detect intent → route to the right subagent (`vc-research-agent`, `vc-innovate-agent`, `vc-plan-agent`, `vc-execute-agent`, etc.). Do not implement code directly for non-trivial work; do answer trivial questions directly.

Process artifacts live in `process/`:
- `process/context/` — project-specific knowledge (router: `all-context.md`)
- `process/features/{feature}/` — feature-scoped plans/reports
- `process/general-plans/` — cross-cutting plans
Read `process/context/all-context.md` first before substantial planning.

## Common commands

The repo is **not a git repository** — don't run git commands.

### Run the app (production-like, single container)

```bash
cp .env.example .env       # edit ALEJANDRIA_SECRET_KEY + admin password
docker compose up -d       # http://localhost:8080  (admin / changeme)
```

### Run the app (dev mode, hot reload)

```bash
docker compose -f docker-compose.dev.yml up
# Frontend (Vite) on :5173 with proxy to backend on :8000
```

### Helper script (preferred for daily work)

`./scripts/dev.sh <cmd>`:
- `start` — production detached
- `dev` — development attached (hot reload)
- `stop`, `logs`, `shell` (bash in container), `rebuild` (no-cache), `reset` (DESTRUCTIVE: deletes library + config)
- `test` — backend pytest (creates `.venv` if missing)
- `test-frontend` — frontend check + vitest
- `calibre-shell` — shows `calibredb --help`

### Backend (Python)

```bash
cd backend
uv pip install -e ".[dev]"          # install with dev extras
pytest -v                           # all tests
pytest tests/test_calibre_db.py     # single test file
pytest --cov=alejandria             # with coverage
ruff check src/alejandria           # lint
mypy src/alejandria                 # type check
uvicorn alejandria.main:app --reload  # local dev server (without Docker)
```

Tests set their own env in `backend/tests/conftest.py` (in-memory DB, `/tmp` paths, `ALEJANDRIA_DEV_MODE=true`) — see fixture pattern for new tests.

### Frontend (SvelteKit)

```bash
cd frontend
npm install
npm run dev         # vite dev :5173
npm run build       # production SPA build (consumed by FastAPI static_path)
npm run check       # svelte-check (TypeScript + Svelte types)
npm run lint        # eslint
npm run test        # vitest
npm run test:e2e    # Playwright
npm run format      # prettier
```

### Quality gates before commit/PR

```bash
# Python
ruff check src/alejandria && mypy src/alejandria && pytest

# Frontend
npm run check && npm run lint && npm test
```

## Architecture (the big picture)

Single container exposes port 8080. FastAPI serves both the JSON/XML API (`/api/*`, `/opds/*`) **and** the prebuilt SvelteKit SPA from `/app/frontend/build`. There is no separate Node process in production — the frontend build is static.

### Two databases, two ownerships

| DB | Path (in container) | Owner | Purpose |
|---|---|---|---|
| App DB | `/config/alejandria.db` | app (read+write) | users, sessions, progress, highlights, shelves, annotations |
| Calibre DB | `/library/metadata.db` | Calibre (read-only by us) | book metadata, covers, tags, series, authors |

`services/calibre_db.py` reads the Calibre DB directly via `sqlite3` — no Calibre binary required for *reads*. The Calibre CLI is only invoked for writes/convert (`calibredb add`, `ebook-convert`, `ebook-meta`). This is a load-bearing distinction: never replace the direct-SQLite read path with a Calibre CLI call.

### Backend layout (`backend/src/alejandria/`)

- `main.py` — FastAPI app factory. Wires 12 routers (see `app.include_router(...)` calls), middleware (GZip, CORS), lifespan (init DB → ensure admin → start scanner), SPA fallback for non-API routes.
- `config.py` — Pydantic settings, env prefix `ALEJANDRIA_`. All paths validated absolute. `calibre_bin_path` auto-detects from common locations.
- `db.py` — SQLAlchemy 2.0 engine/session.
- `models/` — User, Session, Progress, Highlight, Shelf, Annotation. All declared via SQLAlchemy 2.0 declarative style.
- `schemas/` — Pydantic v2 API I/O shapes. Mirror models but only what's exposed.
- `routers/` — `auth, books, library, reader, conversion, kindle, shelves, stats, settings, highlights, opds, health`. OPDS at `/opds/*`, REST at `/api/*`.
- `services/`
  - `calibre_db.py` — direct SQLite reader for Calibre `metadata.db` (load-bearing read path)
  - `scanner.py` — `watchdog` observer that calls `calibredb add` on new files; runs as a background task via `app.state.scanner` started in lifespan
  - `cover.py` — extracts covers from EPUB/PDF/MOBI; falls back to `ebook-meta`
  - `convert.py` — `ebook-convert` wrapper with disk cache at `/config/caches/conversions/{id}/`
  - `smtp.py` — `aiosmtplib` for send-to-Kindle
  - `highlights.py`, `stats.py` — domain services
- `auth/` — `security.py` (argon2 + JWT HS256), `dependencies.py` (FastAPI deps for current user), `oidc.py` (Authentik/Authelia/Keycloak flow).

### Frontend layout (`frontend/src/`)

- `app.html`, `app.css` — shell + 3 themes (warm light `#F5F1E8`, warm dark `#1A1816`, sepia `#F4ECD8`); themes swap via `data-theme` attribute with no FOUC, persisted in `localStorage`.
- `routes/` — SvelteKit pages: `+layout`, `+page` (home), `books/`, `library/`, `login/`, `opds/`, `read/`, `settings/`, `shelves/`, `stats/`.
- `lib/api/` — type-safe fetch wrapper. New backend endpoint → add client method here + TypeScript types in `types.ts`.
- `lib/components/` — Logo, Sidebar, Cover, Toaster, etc.
- `lib/reader/` — EPUB.js + PDF.js wrappers + plain text for FB2/RTF/TXT.
- `lib/stores/` — auth (HttpOnly cookie based), theme.
- SvelteKit uses `adapter-static` with `fallback: 'index.html'` → SPA; FastAPI serves the build and falls back to `index.html` for non-API GETs (see `spa_fallback` in `main.py`).
- Vite dev server proxies `/api` and `/opds` to backend on `:8000` (see `vite.config.ts`).

### Docker (`docker/Dockerfile`)

Multi-stage:
1. `node:20-slim` → builds SvelteKit
2. `debian:bookworm-slim` → installs Calibre CLI via linux-installer (separate stage for layer caching; pinned to `CALIBRE_VERSION=7.13.0`)
3. `python:3.12-slim` → installs Python deps via `uv`
4. Runtime: `python:3.12-slim` + Calibre from stage 2 + Python site-packages from stage 3 + frontend build from stage 1 + `tini` + `gosu` (PUID/PGID remap in entrypoint).

`docker/Dockerfile.dev` is single-stage with hot reload and mounted source volumes (`./backend/src`, `./frontend/src`, `./frontend/static`).

### Data flow patterns

**Reading an EPUB**: `/read/{id}` → `GET /api/reader/{id}/file?fmt=EPUB` → `services/convert.get_readable_file()` returns original file from Calibre library path → EPUB.js loads in browser → progress PUT to `/api/reader/{id}/progress` → `ReadingProgress` row.

**Reading a MOBI** (or any non-native format): `get_readable_file()` → calls `convert()` → shells out to `ebook-convert` → caches at `/config/caches/conversions/{id}/book.epub` → returns cached file on subsequent reads.

**Adding a book**: drop file into `/library/` → `watchdog` event → `LibraryScanner.add_book()` → `calibredb add` → Calibre updates `metadata.db` → next `/api/books` query sees it.

### Auth & security model

- Passwords: argon2id via `passlib`.
- Sessions: HttpOnly + SameSite=Lax cookies carrying JWT (HS256, audience `alejandria`). Server-side `Session` table for revocation.
- CSRF: double-submit pattern (see SvelteKit `csrf.checkOrigin: true` + FastAPI).
- Rate limiting on login (see `auth.py`).
- OIDC: optional, enabled via `OIDC_ENABLED=true` and Authentik/Authelia/Keycloak/Pocket ID.
- PUID/PGID: linuxserver.io convention; entrypoint remaps the in-container `alejandria` user.

### Configuration

Every setting is `ALEJANDRIA_*` env (see `.env.example`). **In production, you must change**: `ALEJANDRIA_SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`) and `ALEJANDRIA_ADMIN_PASSWORD`. `docs/CONFIGURATION.md` has reverse proxy configs (Caddy, nginx, Traefik) and reverse-proxy `client_max_body_size: 500M` for upload support.

### Permissions / volumes (homelab)

`PUID` and `PGID` must match the owner of your `/library` and `/config` directories on the host, otherwise the scanner/Calibre writes fail silently. Test with `./scripts/dev.sh calibre-shell` and check `calibredb list`.

## Adding a feature (the standard path)

1. Add Pydantic schema in `backend/src/alejandria/schemas/`.
2. Add endpoint in the right `routers/` file.
3. Add business logic in `services/` (no Calibre CLI calls in hot paths; reads stay direct-SQLite).
4. Register the router in `main.py` if new.
5. Add client method in `frontend/src/lib/api/client.ts` + types in `types.ts`.
6. Add a route under `frontend/src/routes/` and any components under `lib/components/`.
7. Backend pytest in `backend/tests/`; frontend vitest + Playwright e2e.
8. Update relevant doc in `docs/`.

## Adding a theme

`frontend/src/app.css` defines CSS variables per theme; `tailwind.config.js` wires them. Update `+layout.svelte` (theme switcher) and the auth store if user-selectable.

## Gotchas

- **Calibre binary location**: `config.calibre_bin_path` searches a fixed allowlist and falls back to bare `calibredb` on `$PATH`. In Docker it's `/opt/calibre/calibredb` (added via `ENV PATH`). Don't hardcode it.
- **OPDS auth**: OPDS clients use HTTP Basic Auth → only safe behind HTTPS. The reader endpoint supports HTTP Range requests (used by KOReader, Calibre Companion).
- **Scanner is started in lifespan, not on first request**: don't `await` it from request handlers.
- **App DB schema changes**: this repo doesn't use Alembic yet; new models require `Base.metadata.create_all` on existing DBs or manual migrations. Check current state before assuming auto-migrate.
- **OPDS at `/opds`, REST at `/api`**: keep them separate in the SPA fallback exclusion list in `main.py`.
- **Calibre DB reads are case-sensitive on filenames**; `services/calibre_db.py` normalizes paths.
- **Multi-stage Docker layer cache**: bumping `CALIBRE_VERSION` or `frontend/package*.json` invalidates downstream layers — the dev image (single stage) doesn't have this caching and is faster for iteration but bigger.
- **`.gitignore` excludes `library/`, `config/`, `covers/`**: never commit user library data.

## Project metadata

- Version: `0.1.0` (see `backend/src/alejandria/__init__.py` and `frontend/package.json`).
- License: MIT for our code. The Calibre CLI binary inside the container is GPL-3 (separate, see `LICENSE`).
- Docs: `README.md`, `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `docs/OPDS.md`, `docs/CONTRIBUTING.md`.
- Contributing flow / Conventional Commits / release process: see `docs/CONTRIBUTING.md`.
