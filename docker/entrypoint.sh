#!/bin/bash
# =============================================================================
# Alejandría entrypoint
# - Apply PUID/PGID for homelab compatibility
# - Refuse PUID=0 by default (defence-in-depth: avoid running as root)
# - Fix permissions on volumes (bounded find sweep + marker file)
# - Hand off to main process
# =============================================================================
set -euo pipefail

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# --- B5: refuse to run as root unless explicitly allowed. ---
if [[ "${ALEJANDRIA_ALLOW_ROOT:-}" != "true" ]]; then
    if [[ "$PUID" == "0" || "$PGID" == "0" ]]; then
        echo "ERROR: PUID/PGID=0 is not allowed." >&2
        echo "       The app refuses to run as root inside the container." >&2
        echo "       Fix: set PUID/PGID to match the owner of ./library and ./config." >&2
        echo "       Override (only for trusted system containers): set ALEJANDRIA_ALLOW_ROOT=true" >&2
        exit 1
    fi
else
    echo "WARNING: ALEJANDRIA_ALLOW_ROOT=true - running as root inside the container." >&2
    echo "         This is a defence-in-depth bypass; only use it for system containers." >&2
fi

if [ "$(id -u alejandria)" != "$PUID" ]; then
    echo "Adjusting alejandria user to UID=$PUID GID=$PGID"
    groupmod -o -g "$PGID" alejandria
    usermod -o -u "$PUID" alejandria
fi

# --- B7: chown performance fix. ---
# Mark perms-applied the first time we fix them; subsequent boots skip the
# find sweep when nothing has changed.
PERMS_MARKER="/config/.alejandria-perms-applied"
if [[ ! -f "$PERMS_MARKER" ]]; then
    # Non-recursive on roots: O(1).
    chown "$PUID:$PGID" /library /config /app 2>/dev/null || true
    # Then fix the rest with a bounded find sweep.
    find /library /config -maxdepth 2 ! -user "$PUID" -exec chown "$PUID:$PGID" {} + 2>/dev/null || true
    touch "$PERMS_MARKER"
fi

if [ "$(id -u)" = "0" ]; then
    exec gosu alejandria "$@"
else
    exec "$@"
fi
