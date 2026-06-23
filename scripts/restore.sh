#!/bin/bash
# =============================================================================
# Alejandría restore helper.
#
# Usage:
#   ./scripts/restore.sh --source DIR [--target PATH] [--force]
#
# Defaults:
#   --target   ./ (the current dir)
#   --force    false (will prompt before overwriting library/config)
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$REPO_ROOT"
FORCE=""
SOURCE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            SOURCE="$2"
            shift 2
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --force)
            FORCE="1"
            shift
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

if [[ -z "${SOURCE:-}" ]]; then
    echo "ERROR: --source DIR is required." >&2
    exit 2
fi

if [[ ! -d "$SOURCE" ]]; then
    echo "ERROR: $SOURCE does not exist." >&2
    exit 1
fi

MANIFEST="$SOURCE/MANIFEST.txt"
SNAPSHOT_DB="$SOURCE/alejandria.db.snapshot"
LIBRARY_TAR="$SOURCE/library.tar.gz"
CONFIG_TAR="$SOURCE/config.tar.gz"

if [[ ! -f "$MANIFEST" ]]; then
    echo "ERROR: $MANIFEST missing. Refusing to restore without a manifest." >&2
    exit 1
fi
if [[ ! -f "$SNAPSHOT_DB" && ! -f "$LIBRARY_TAR" && ! -f "$CONFIG_TAR" ]]; then
    echo "ERROR: No snapshot files found in $SOURCE." >&2
    exit 1
fi

echo "Manifest:"
cat "$MANIFEST"
echo "---"

if [[ -z "$FORCE" ]]; then
    echo "About to restore to $TARGET."
    echo "This may overwrite existing library/ and config/ directories."
    read -rp "Type 'yes' to continue: " answer
    if [[ "$answer" != "yes" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

mkdir -p "$TARGET"

# Stop the app first if Docker is around.
if command -v docker >/dev/null 2>&1; then
    if docker compose ps --services 2>/dev/null | grep -q alejandria; then
        echo "Stopping the app container ..."
        (cd "$TARGET" && docker compose down)
    fi
fi

# Restore the app DB snapshot (WAL-safe).
if [[ -f "$SNAPSHOT_DB" ]]; then
    echo "Restoring app DB snapshot ..."
    cp "$SNAPSHOT_DB" "$TARGET/config/alejandria.db"
    # Remove any stale WAL/SHM — the snapshot is a fresh checkpoint.
    rm -f "$TARGET/config/alejandria.db-wal" "$TARGET/config/alejandria.db-shm"
fi

# Restore library + config.
if [[ -f "$LIBRARY_TAR" ]]; then
    echo "Restoring library/ ..."
    tar -xzf "$LIBRARY_TAR" -C "$TARGET"
fi
if [[ -f "$CONFIG_TAR" ]]; then
    echo "Restoring config/ ..."
    tar -xzf "$CONFIG_TAR" -C "$TARGET"
fi

echo "Restore complete. Start the app with: docker compose up -d"
