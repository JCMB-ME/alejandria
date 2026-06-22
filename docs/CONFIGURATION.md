# Configuration

All configuration is via environment variables. See [`.env.example`](../.env.example) for the full list.

## Required

| Variable | Description |
|----------|-------------|
| `ALEJANDRIA_SECRET_KEY` | Long random string for JWT signing. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ALEJANDRIA_ADMIN_PASSWORD` | Initial admin password (change after first login!) |

## Server

| Variable | Default | Description |
|----------|---------|-------------|
| `ALEJANDRIA_HOST` | `0.0.0.0` | Bind address |
| `ALEJANDRIA_PORT` | `8080` | HTTP port |
| `ALEJANDRIA_BASE_URL` | `http://localhost:8080` | Public URL (for OPDS links) |

## Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `ALEJANDRIA_LIBRARY_PATH` | `/library` | Where your books live (Calibre structure) |
| `ALEJANDRIA_CONFIG_PATH` | `/config` | App config, DB, caches |
| `ALEJANDRIA_DB_PATH` | `/config/alejandria.db` | App database file |

## PUID/PGID (homelab)

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `1000` | User ID for the app process |
| `PGID` | `1000` | Group ID |
| `TZ` | `UTC` | Timezone |

These follow the [linuxserver.io](https://docs.linuxserver.io/general/understanding-puid-and-pgid) convention. Set them to match the owner of your library directory to avoid permission issues.

## Calibre

| Variable | Default | Description |
|----------|---------|-------------|
| `ALEJANDRIA_ENABLE_CALIBRE` | `true` | Use Calibre CLI for conversion/metadata |
| `CALIBRE_BIN` | (auto) | Path to `calibredb` if not in default location |

## Send-to-Kindle (SMTP)

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | Usually `587` (TLS) or `465` (SSL) |
| `SMTP_USERNAME` | SMTP auth username |
| `SMTP_PASSWORD` | SMTP auth password (use app password for Gmail) |
| `SMTP_FROM_EMAIL` | From address |
| `SMTP_USE_TLS` | `true` for STARTTLS, `false` for SSL on port 465 |
| `KINDLE_EMAILS` | Comma-separated default Kindle recipients |

**Gmail users**: create an [App Password](https://support.google.com/accounts/answer/185833) and use it as `SMTP_PASSWORD`.

Don't forget to add your sending address to your Kindle's [Approved Senders list](https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJGSBGJSXC4ZB).

## Web scraper

All scraper settings use the `ALEJANDRIA_SCRAPER_*` prefix. See
[`SCRAPER.md`](SCRAPER.md) for the user-facing guide.

| Variable | Default | Description |
|----------|---------|-------------|
| `ALEJANDRIA_SCRAPER_ENABLED` | `true` | Master switch for the scraper subsystem. Set to `false` to disable. |
| `ALEJANDRIA_SCRAPER_OUTPUT_DIR` | `/config/scrapes` | Where downloaded pages and assembled outputs are written. |
| `ALEJANDRIA_SCRAPER_MAX_CONCURRENT_JOBS` | `2` | Max simultaneous browser contexts. |
| `ALEJANDRIA_SCRAPER_MAX_PAGES_PER_JOB` | `2000` | Hard cap on pages per job. |
| `ALEJANDRIA_SCRAPER_DEFAULT_DELAY_MS` | `500` | Inter-page delay (overridable per YAML adapter). |
| `ALEJANDRIA_SCRAPER_MAX_TOTAL_SIZE_MB` | `500` | Hard cap on total image bytes per job. |
| `ALEJANDRIA_SCRAPER_BROWSER_HEADLESS` | `true` | Set `false` to run Chromium with a window (debug). |
| `ALEJANDRIA_SCRAPER_ADAPTERS_FILE` | `/config/site-adapters.yaml` | YAML adapter definitions file. |
| `ALEJANDRIA_SCRAPER_PROXY` | `""` | Optional HTTP/SOCKS5 proxy URL passed to Playwright + aiohttp. |
| `ALEJANDRIA_SCRAPER_USER_AGENT` | Chrome 120 | Default browser user-agent. |
| `ALEJANDRIA_SCRAPER_MAX_JOBS_PER_HOUR` | `10` | Per-user rate limit. Set to `0` or empty to disable. |

## OIDC (optional SSO)

| Variable | Description |
|----------|-------------|
| `OIDC_ENABLED` | `true` to enable |
| `OIDC_ISSUER` | e.g. `https://auth.yourdomain.com/application/o/alejandria/` |
| `OIDC_CLIENT_ID` | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | OAuth2 client secret |
| `OIDC_REDIRECT_URI` | e.g. `https://alejandria.yourdomain.com/api/auth/oidc/callback` |

Tested with: Authentik, Authelia, Keycloak, Pocket ID.

## Adding books

### Option A: copy files in

```bash
docker exec -u 1000:1000 alejandria calibredb add --library-path /library /library/imported
```

### Option B: mount existing Calibre library

If you already have a Calibre library on disk, just mount it:

```yaml
volumes:
  - /path/to/your/Calibre Library:/library
```

On first start, Alejandría reads `metadata.db` directly — your existing library is immediately browsable.

### Option C: in-app upload

Coming soon: drag-and-drop upload to a watched import folder.

## Reverse proxy

### Caddy

```caddy
alejandria.yourdomain.com {
    reverse_proxy localhost:8080
}
```

### nginx

```nginx
location / {
    proxy_pass http://localhost:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 500M;  # for book uploads
}
```

### Traefik

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.alejandria.rule=Host(`alejandria.example.com`)"
  - "traefik.http.routers.alejandria.entrypoints=websecure"
  - "traefik.http.routers.alejandria.tls.certresolver=letsencrypt"
  - "traefik.http.services.alejandria.loadbalancer.server.port=8080"
```
