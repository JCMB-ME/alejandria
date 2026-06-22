# Alejandría Backend

FastAPI + SQLAlchemy + Calibre metadata.db reader.

## Architecture

```
src/alejandria/
├── __main__.py           # CLI entrypoint
├── main.py               # FastAPI app factory
├── config.py             # Pydantic settings (env-based)
├── db.py                 # SQLAlchemy engine + session
├── models/               # SQLAlchemy models
│   ├── user.py
│   ├── session.py
│   ├── progress.py
│   ├── highlight.py
│   ├── shelf.py
│   └── annotation.py
├── schemas/              # Pydantic schemas (API I/O)
│   ├── book.py
│   ├── user.py
│   └── ...
├── routers/              # FastAPI routers
│   ├── auth.py           # /api/auth/*
│   ├── books.py          # /api/books/*
│   ├── library.py        # /api/library/*
│   ├── reader.py         # /api/reader/*
│   ├── conversion.py     # /api/convert/*
│   ├── kindle.py         # /api/kindle/*
│   ├── opds.py           # /opds/*
│   └── health.py         # /api/health
├── services/             # Business logic
│   ├── calibre_db.py     # Read Calibre metadata.db directly
│   ├── scanner.py        # Watch + rescan library
│   ├── cover.py          # Cover extraction + cache
│   ├── convert.py        # Calibre ebook-convert wrapper
│   ├── smtp.py           # Send-to-Kindle via SMTP
│   ├── highlights.py     # Highlights CRUD
│   ├── stats.py          # Reading stats
│   └── recommender.py    # Tag-based recommender
├── auth/                 # Authentication
│   ├── security.py       # Argon2 + JWT
│   ├── dependencies.py   # FastAPI deps
│   └── oidc.py           # OIDC flow
└── utils/
    ├── paths.py
    ├── files.py
    └── log.py
```

## Database

Two databases:
1. **App DB** (`alejandria.db`) — users, sessions, progress, highlights, shelves
2. **Calibre DB** (`metadata.db`) — read-only access to user's existing library

## Dev

```bash
uv pip install -e ".[dev]"
uvicorn alejandria.main:app --reload
```
