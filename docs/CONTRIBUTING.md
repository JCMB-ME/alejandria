# Contributing to Alejandría

Thanks for your interest in making Alejandría better.

## Quick start (development)

```bash
# 1. Clone
git clone https://github.com/your-user/alejandria.git
cd alejandria

# 2. Copy env
cp .env.example .env
# Edit .env to set ALEJANDRIA_SECRET_KEY and ALEJANDRIA_ADMIN_PASSWORD

# 3. Run with Docker (production-like)
docker compose up -d

# OR for development with hot reload:
docker compose -f docker-compose.dev.yml up
```

Then open `http://localhost:8080` (prod) or `http://localhost:5173` (dev with Vite proxying to backend on :8000).

## Project layout

```
alejandria/
├── backend/          Python 3.12 + FastAPI
│   ├── pyproject.toml
│   ├── src/alejandria/
│   │   ├── main.py             FastAPI app
│   │   ├── config.py           Pydantic settings
│   │   ├── db.py               SQLAlchemy engine
│   │   ├── models/             App DB models
│   │   ├── schemas/            Pydantic API schemas
│   │   ├── routers/            FastAPI routers
│   │   ├── services/           Business logic
│   │   ├── auth/               Authentication
│   │   └── utils/              Helpers
│   └── tests/
├── frontend/         SvelteKit 2 + Svelte 5
│   ├── package.json
│   ├── src/
│   │   ├── routes/             Pages
│   │   ├── lib/
│   │   │   ├── api/            Type-safe API client
│   │   │   ├── components/     Reusable UI
│   │   │   ├── stores/         Svelte stores
│   │   │   └── reader/         Reader-specific helpers
│   │   ├── app.html
│   │   └── app.css
│   └── static/
├── docker/
│   ├── Dockerfile              Production
│   ├── Dockerfile.dev          Development
│   ├── entrypoint.sh
│   └── entrypoint.dev.sh
└── docs/
```

## Code style

- Python: `ruff` for linting + formatting, `mypy` for types. Run `ruff check` and `mypy src/alejandria`.
- TypeScript/Svelte: `prettier` + `eslint`. Run `npm run lint` and `npm run check`.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (enforced by CI).
- Line length: 100 (Python), 100 (TS/Svelte).

## Adding a feature

1. Open an issue describing the feature (or pick an existing one).
2. Create a branch: `git checkout -b feat/your-feature`.
3. Make your changes.
4. Add tests where it makes sense.
5. Update the relevant docs.
6. Open a PR.

## Adding a new API endpoint

1. Add a Pydantic schema in `backend/src/alejandria/schemas/`.
2. Add the endpoint in the appropriate router in `backend/src/alejandria/routers/`.
3. If new business logic, add a service in `services/`.
4. Add the client method in `frontend/src/lib/api/client.ts`.
5. Add TypeScript types in `frontend/src/lib/api/types.ts`.

## Adding a new theme

Edit `frontend/src/app.css` and `frontend/tailwind.config.js`. Add CSS variables in `:root`, `[data-theme='dark']`, and any new theme selector. Then update `src/lib/stores/auth.ts` if the new theme is user-selectable.

## Testing

```bash
# Backend
cd backend
uv pip install -e ".[dev]"
pytest
pytest --cov=alejandria  # with coverage

# Frontend
cd frontend
npm run check    # type check
npm run test     # unit tests
npm run test:e2e # Playwright e2e
```

## Release process

1. Update `__version__` in `backend/src/alejandria/__init__.py` and `package.json`.
2. Update `CHANGELOG.md`.
3. Tag: `git tag -a v0.x.y -m "Release v0.x.y"`.
4. Push tags: `git push --tags`.
5. CI builds and pushes the Docker image.
6. Update the release on GitHub.

## Code of conduct

Be kind. This is a hobby project. We're all here to build something nice for our book-hoarding friends.

## License

By contributing, you agree your contributions will be licensed under the MIT License.
