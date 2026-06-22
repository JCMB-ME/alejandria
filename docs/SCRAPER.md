# Web Scraper

The web scraper turns paginated online books (image scans, comics, or simple
readers) into PDF, EPUB, or CBZ files you can read in Alejandría or download.

## What it is

A logged-in user pastes a URL. The server uses headless Chromium to walk the
pages, download every page image, then assemble the result into one or more of:

- **PDF** — lossless, assembled with `img2pdf`.
- **EPUB** — fixed-layout, one `<img>` per XHTML page, built with `ebooklib`.
- **CBZ** — Comic Book Zip, built with the stdlib `zipfile` module.

The assembled file is either **imported into the Calibre library** (via
`calibredb add`) and/or **left downloadable** through a per-job download URL.

## What it isn't

- It does **not** bypass anti-bot protection. Cloudflare, Turnstile, DataDome
  and similar services WILL block the scraper. The default adapter detects
  empty body content and surfaces a friendly error.
- It does **not** crawl whole sites or extract a TOC from chapter pages.
- It does **not** OCR page images to text.
- It does **not** enforce copyright policy. **Only scrape content you have
  the right to download.** A disclaimer is shown in the UI and the README.

## Quick start

1. Sign in.
2. On the home page, find the "Web scraper" block.
3. Paste a URL like `https://example.com/book/1`.
4. Pick output formats (PDF / EPUB / CBZ) and destinations (library /
   download).
5. Click **Start scrape**.
6. Watch the progress bar. Active jobs are polled every 2 s.
7. When the job is **Done**, click **Download** to save the file, or
   **Open in library** if you chose the library destination.

## Default `generic` adapter

The built-in adapter uses a few heuristics to find page images and "next" links:

- Picks the largest `<img>` elements (>= 200x200) on the page.
- Also scans for CSS `background-image: url(...)` declarations.
- For the "next" page, tries in order: `<a rel="next">`, link text matching
  "next" / "siguiente" / "→" / ">" (English and Spanish), URL increment
  (e.g. `/1/` → `/2/`), and an in-page scroll fallback.

If `generic` does not work for your site, write a YAML adapter.

## YAML adapters

YAML adapters let you configure the scraper for specific sites without code
changes. The default adapters file is `/config/site-adapters.yaml` (override
with `ALEJANDRIA_SCRAPER_ADAPTERS_FILE`).

### Schema

```yaml
adapters:
  - name: <unique-name>                 # required
    url_regex: '^https?://...'          # required
    image_selector: 'div.reader img'    # CSS selector; default: "img.large, #page-img"
    next_selector: 'a.next'             # CSS selector or null
    pagination_style: click             # one of: click, url_increment, infinite_scroll
    delay_ms_between_requests: 800      # default 500
    user_agent: "Mozilla/5.0 ..."       # override the request UA
    cookies:                             # static cookie jar
      session: "PASTE-YOUR-COOKIE"
    headers:                             # static headers
      Referer: "https://example.com/"
    requires_auth: true                  # informational; no behavior change in v1
```

If the file does not exist, the scraper logs a debug message and falls back
to the generic adapter. Sample adapters are shipped in
[`process/features/scraper/references/EXAMPLE_ADAPTERS.yaml`](../process/features/scraper/references/EXAMPLE_ADAPTERS.yaml).

### Walk-through

1. **Pick a `url_regex`** that matches every book URL on the target site. The
   regex is searched (not anchored at the end), so `^https?://foo\.example/`
   is fine.
2. **Open one chapter in DevTools.** Inspect the page; find the CSS selector
   that matches the page image (e.g. `div.reader img`).
3. **Find the "next" element.** If it is an `<a>` with a `href`, use a
   selector that matches it. If there is no link but the URL increments,
   set `pagination_style: url_increment`.
4. **Test the adapter** by clicking the **Test adapter** button in the panel.
   It will show you the image candidates and the next-button candidates it
   found.
5. **Submit the adapter file** to `/config/site-adapters.yaml` (or mount it
   differently in your container) and restart the app.

## Configuration (env vars)

All settings are `ALEJANDRIA_SCRAPER_*` env vars:

| Variable | Default | Description |
|---|---|---|
| `ALEJANDRIA_SCRAPER_ENABLED` | `true` | Master switch. |
| `ALEJANDRIA_SCRAPER_OUTPUT_DIR` | `/config/scrapes` | Where to write downloaded pages and outputs. |
| `ALEJANDRIA_SCRAPER_MAX_CONCURRENT_JOBS` | `2` | Max simultaneous browser contexts. |
| `ALEJANDRIA_SCRAPER_MAX_PAGES_PER_JOB` | `2000` | Hard cap on pages per job. |
| `ALEJANDRIA_SCRAPER_DEFAULT_DELAY_MS` | `500` | Inter-page delay (per adapter override). |
| `ALEJANDRIA_SCRAPER_MAX_TOTAL_SIZE_MB` | `500` | Hard cap on total image bytes per job. |
| `ALEJANDRIA_SCRAPER_BROWSER_HEADLESS` | `true` | Set `false` to run Chromium with a window (debug). |
| `ALEJANDRIA_SCRAPER_ADAPTERS_FILE` | `/config/site-adapters.yaml` | YAML adapter definitions. |
| `ALEJANDRIA_SCRAPER_PROXY` | `""` | Optional HTTP/SOCKS5 proxy URL. |
| `ALEJANDRIA_SCRAPER_USER_AGENT` | Chrome 120 | Default browser user-agent. |
| `ALEJANDRIA_SCRAPER_MAX_JOBS_PER_HOUR` | `10` | Per-user rate limit. |

## Security

- **SSRF protection** — every URL is checked against a blocklist of
  loopback / private / link-local / CGNAT / IPv6 ULA ranges. Non-HTTP schemes
  (`file://`, `ftp://`, `data:`, `javascript:`, ...) are rejected with HTTP
  400 before any network egress.
- **Rate limiting** — a user can submit at most 10 jobs per hour.
- **Per-image cap** — 50 MB max bytes and 6000 px max dimension per image.
  Pillow only reads the image header (~64 KB) to check dimensions; the
  full bitmap is never decoded by the scraper.
- **Per-job cap** — 2000 pages max, 500 MB total bytes max.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| 400 "URL targets a private or loopback address" | Site is on a private network | Only scrape public sites. |
| 429 "Rate limit exceeded" | Too many jobs in the last hour | Wait, or raise `ALEJANDRIA_SCRAPER_MAX_JOBS_PER_HOUR`. |
| Job marked `failed` with "Image too large" | One page is > 6000 px or > 50 MB | Lower the source image size, or raise the cap. |
| Job marked `failed` with "max total size" | Total > 500 MB | Raise `ALEJANDRIA_SCRAPER_MAX_TOTAL_SIZE_MB` or split into smaller jobs. |
| Job stuck on `queued` | Manager not started | Check logs for `scraper_manager_start_failed`; ensure Playwright Chromium is installed. |
| 0 images found | Generic adapter heuristic missed the page | Click **Test adapter**, then write a YAML adapter. |
| Anti-bot page returned (Cloudflare, etc.) | The site blocks headless browsers | Not supported in v1. |

## Limitations (v1)

- No anti-bot bypass (Cloudflare, Turnstile, DataDome, etc.).
- No per-chapter TOC; the scraper walks whatever the adapter returns.
- Fixed-layout EPUB assumes the first image's aspect ratio for the whole
  book. Mixed-aspect jobs may look stretched on a few pages.
- No resume from partial scrape after a server crash — crashed jobs are
  marked `failed` with the message "Server restarted while job was running".
- `importing_library` is part of the `packaging` state; there is no separate
  `importing` status in v1.

## Disabling the scraper

Set `ALEJANDRIA_SCRAPER_ENABLED=false` and restart the app. The ScraperPanel
hides itself automatically (because the API returns 503 and the list call
fails silently).
