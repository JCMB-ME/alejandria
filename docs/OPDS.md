# OPDS Setup

Alejandría exposes an OPDS 1.2 catalog at `/opds`. This is compatible with most e-reader companion apps.

## Catalog URL

```
http://your-host:8080/opds
```

For HTTPS deployments:
```
https://alejandria.yourdomain.com/opds
```

## Tested clients

| App | Platform | Status |
|-----|----------|--------|
| [KOReader](https://koreader.rocks/) | e-ink (Kobo, Kindle, PocketBook) | ✓ Works |
| [Calibre Companion](https://www.calibre-companion.com/) | iOS, Android | ✓ Works |
| [Moon+ Reader](https://www.moondownload.com/) | Android | ✓ Works |
| [Marvin](https://marvinapp.com/) | iOS | ✓ Works |
| Cantook | iOS, Android | ✓ Works |
| KyBook 3 | iOS | ✓ Works |

## Client setup

### KOReader

1. Open KOReader
2. Main menu → "Tools" → "OPDS catalog"
3. Add new catalog
4. Enter URL: `http://your-host:8080/opds`
5. Enter your Alejandría username + password
6. Browse, download books directly to your device

### Calibre Companion (iOS/Android)

1. Open Calibre Companion
2. Tap "+" → "Add a new connection"
3. Type: OPDS
4. URL: `http://your-host:8080/opds`
5. Username/password
6. Browse library, tap book to download

### Moon+ Reader (Android)

1. Open Moon+
2. Menu → "My books" → Network
3. Add OPDS catalog
4. URL + credentials

## Authentication

OPDS requires authentication by default. Clients (KOReader, Calibre Companion) use HTTP Basic Auth. The `ALEJANDRIA_OPDS_REQUIRE_AUTH` opt-out is for trusted LANs only.

## Search

The OPDS catalog supports OpenSearch. Clients that respect it will let you search across the entire library:

```
/opds/search?q=your+query
```

## Format support

OPDS exposes all formats a book has. The reader app picks its preferred one. For example:
- KOReader on Kindle prefers MOBI / AZW3
- Marvin prefers EPUB
- Moon+ PDF reader prefers PDF

If a book only has MOBI and your client prefers EPUB, the file will be served as MOBI — the client converts if needed, or you can use the web reader which auto-converts via Calibre.

## Streams / Range requests

Alejandría's `/api/reader/{id}/file` endpoint supports HTTP Range requests, so large books can be streamed in chunks. This is what KOReader and Calibre Companion use for fast browsing.

## OPDS 2.0 (Readium)

Not yet implemented. OPDS 1.2 covers the vast majority of clients. OPDS 2.0 / Readium Web Pub Manifest is on the roadmap — if you need it, [open an issue](https://github.com/your-user/alejandria/issues).
