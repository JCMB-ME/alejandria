#!/bin/bash
# =============================================================================
# Alejandría backup helper.
#
# Produces a snapshot of the library and config directories plus a
# consistent copy of the app DB (WAL-safe via sqlite3 .backup).
#
# Usage:
#   ./scripts/backup.sh [--target DIR] [--incremental PREV]
#
# Defaults:
#   --target     ./backups/<UTC timestamp>
#   --incremental none (full snapshot)
#
# Run from the repo root. The script must NOT be run inside the container;
# it operates on the bind-mounted host directories.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="./backups/$(date -u +%Y%m%dT%H%M%SZ)"
INCREMENTAL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --incremental)
            INCREMENTAL="$2"
            shift 2
            ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown arg: $1" >&2
            exit 2
            ;;
    esac
done

LIBRARY="$REPO_ROOT/library"
CONFIG="$REPO_ROOT/config"
APP_DB="$CONFIG/alejandria.db"

if [[ ! -d "$LIBRARY" ]]; then
    echo "ERROR: $LIBRARY does not exist. Run from the repo root." >&2
    exit 1
fi
if [[ ! -d "$CONFIG" ]]; then
    echo "ERROR: $CONFIG does not exist. Run from the repo root." >&2
    exit 1
fi

mkdir -p "$TARGET"
echo "Backing up to $TARGET ..."

# 1. Consistent snapshot of the app DB via sqlite3 .backup (WAL-safe).
SNAPSHOT_DB="$TARGET/alejandria.db.snapshot"
if [[ -f "$APP_DB" ]]; then
    if ! command -v sqlite3 >/dev/null 2>&1; then
        echo "ERROR: sqlite3 CLI not found in PATH. Install it or use your package manager." >&2
        exit 1
    fi
    # Checkpoint first to minimise WAL lag.
    sqlite3 "$APP_DB" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null
    sqlite3 "$APP_DB" ".backup '$SNAPSHOT_DB'"
    echo "  app DB snapshot: $SNAPSHOT_DB"
else
    echo "  app DB not found at $APP_DB - skipping (fresh install?)"
fi

# 2. tar the library.
echo "  archiving library/ ..."
tar -czf "$TARGET/library.tar.gz" -C "$REPO_ROOT" library

# 3. tar the config minus the live DB (already snapshotted) and minus caches
#    that are safe to rebuild.
echo "  archiving config/ ..."
tar -czf "$TARGET/config.tar.gz" \
    --exclude="config/alejandria.db" \
    --exclude="config/alejandria.db-wal" \
    --exclude="config/alejandria.db-shm" \
    -C "$REPO_ROOT" config

# 4. Manifest with hashes and sizes.
{
    echo "alejandria_backup_manifest"
    echo "created_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "incremental_from=$INCREMENTAL"
    echo "---"
    for f in "$SNAPSHOT_DB" "$TARGET/library.tar.gz" "$TARGET/config.tar.gz"; do
        if [[ -f "$f" ]]; then
            sz=$(stat -c '%s' "$f" 2>/dev/null || stat -f '%z' "$f")
            sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$f" | awk '{print $1}')
            echo "file=$(basename "$f") size=$sz sha256=$sha"
        fi
    done
} > "$TARGET/MANIFEST.txt"

echo "Done. Manifest:"
cat "$TARGET/MANIFEST.txt"
