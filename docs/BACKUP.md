# Backups

**Audience**: anyone running Alejandría in production. Read this once, then automate it.

## TL;DR

Two directories need backing up:

| Directory | Contains | Frequency | Why |
|---|---|---|---|
| `./library/` | Calibre books + `metadata.db` | Weekly (or whenever you add books) | Books are the irreplaceable part. Losing this is "the library is gone". |
| `./config/` | `alejandria.db` (app DB), `alejandria.db-wal`, `alejandria.db-shm`, caches, scrapes | Daily | Users, sessions, reading progress, highlights, shelves, scrape history. Small (typically <100 MB). |

## What lives where

### `./library/`

The Calibre-managed library directory. Calibre stores:

- Book files (`Author/Title (id)/file.ext` layout)
- `metadata.db` — SQLite database with the library index
- `.caltrash/` — Calibre's own deleted-book holding pen (transient)
- `*.opf` files — per-book metadata

Calibre writes to `metadata.db` on every scan, every metadata edit, and every `calibredb add`. A hot copy of `metadata.db` *can* be inconsistent if you `cp` while Calibre is writing — Calibre's DB uses default journal mode (DELETE), so a hot copy is safer than the app DB but not guaranteed-consistent.

### `./config/`

The app's runtime state directory:

- `alejandria.db` — SQLite app DB (users, sessions, progress, highlights, shelves, annotations, scrape jobs)
- `alejandria.db-wal` — SQLite Write-Ahead Log (recent uncommitted writes)
- `alejandria.db-shm` — SQLite shared memory file
- `caches/` — cover thumbnails, converted book caches, conversion temp files
- `scrapes/` — scraper output (in-progress + completed EPUB/CBZ/PDF files)
- `site-adapters.yaml` — user-edited scraper adapter list
- `logs/` — log files (only if `ALEJANDRIA_LOG_FILE=` is set; empty otherwise)

**The app DB uses WAL mode**, so the `*.db-wal` file holds recent writes that haven't been checkpointed into the main DB file. **You must back up all three (`*.db`, `*.db-wal`, `*.db-shm`) atomically** — losing any of them can corrupt the DB on next open.

## Pre-update snapshot recipe

Before any `docker compose pull && up -d`, snapshot both directories:

```bash
cp -a ./library ./library.bak.$(date +%F)
cp -a ./config ./config.bak.$(date +%F)
```

`cp -a` preserves permissions and uses reflink-on-write on supporting filesystems. The snapshots are full copies; for incremental backups, use the helper script below.

## Automated backup (recommended)

Run the included `scripts/backup.sh` daily (cron, systemd timer, or a `linuxserver/cron` sidecar):

```bash
./scripts/backup.sh --target /backups/alejandria
```

What it does:

1. Checkpoints the app DB (WAL -> main DB) so the `.backup` snapshot is complete.
2. Calls `sqlite3 .backup` to produce a consistent copy of the app DB at `<target>/alejandria.db.snapshot`. This works correctly under WAL mode.
3. `tar -czf` the library directory.
4. `tar -czf` the rest of the config directory (excluding the live DB; the snapshot already covers it).
5. Writes a `MANIFEST.txt` with versions, sizes, SHA-256 hashes.
6. Exits non-zero if any step fails.

For incremental backups, run with `--incremental /path/to/last-backup`. Hard-links unchanged files from the previous backup.

## Restore procedure

```bash
# 1. Stop the app.
docker compose down

# 2. Restore.
./scripts/restore.sh --source /backups/alejandria/2026-06-23

# 3. Verify the manifest matches what you expect (timestamps, hashes).
cat /backups/alejandria/2026-06-23/MANIFEST.txt

# 4. Start the app.
docker compose up -d

# 5. Log in and spot-check: library list, highlights, shelves.
```

`scripts/restore.sh` will **refuse** to overwrite `./library` or `./config` unless `--force` is passed, and prints a confirmation prompt.

## Disaster recovery: I lost everything

If `./library` and `./config` are both gone:

1. **Reinstall** Alejandría: `git clone` the repo, `cp .env.example .env`, edit secrets.
2. **Don't** start the app yet.
3. **Restore from backup**: `./scripts/restore.sh --source /backups/alejandria/<date> --force`.
4. **If you have a library backup but no config backup**: the library will reappear with books, but users, progress, highlights, and shelves are gone. Re-create the admin user via the SPA's first-run setup screen.
5. **If you have a config backup but no library backup**: the app boots into an empty library. Books can be re-added one at a time via upload or by re-mounting your filesystem elsewhere and running `calibredb add --automerge overwrite` for each.
6. **If neither backup exists**: the library is gone. Re-add books manually.

## Backup frequency recommendations

| Use case | Library | Config |
|---|---|---|
| Casual (1 user, occasional adds) | Weekly | Daily |
| Active (5+ users, regular adds) | Daily | Hourly |
| Family library (irreplaceable highlights) | Daily + weekly offsite | Hourly + daily offsite |

Offsite = a different physical machine, an S3-compatible bucket via `restic`/`borgbackup`, or a tape rotation. Local-only backups protect against file corruption but not against fire/flood/theft.

## Tools

- **`scripts/backup.sh`** — ships with the repo. Self-contained; needs `bash`, `tar`, `sqlite3`.
- **restic** / **borgbackup** — incremental, encrypted, deduplicated. Use these for offsite.
- **`linuxserver/cron`** — a tiny sidecar container that runs cron jobs in a Docker-native setup.

## Why `sqlite3 .backup` and not `cp`

`cp alejandria.db /backup/alejandria.db` copies the main file. If the app is mid-write to the WAL file at the moment of copy, the main file is missing the last few seconds of committed transactions. Worse: `rsync --delete` may remove the `.db-wal` file because it didn't exist on the destination yet — corrupting the DB on next open.

`sqlite3 .backup` opens a second connection, runs `BEGIN`, copies all pages in a single transaction, and commits. The result is a consistent snapshot regardless of concurrent writes.
