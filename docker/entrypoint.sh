#!/bin/bash
# =============================================================================
# Alejandría entrypoint
# - Apply PUID/PGID for homelab compatibility
# - Fix permissions on volumes
# - Hand off to main process
# =============================================================================
set -e

# Apply PUID/PGID if set
PUID=${PUID:-1000}
PGID=${PGID:-1000}

if [ "$(id -u alejandria)" != "$PUID" ]; then
    echo "Adjusting alejandria user to UID=$PUID GID=$PGID"
    groupmod -o -g "$PGID" alejandria
    usermod -o -u "$PUID" alejandria
fi

# Fix permissions on volumes
chown -R alejandria:alejandria /library /config /app 2>/dev/null || true

# Switch to user and run
if [ "$(id -u)" = "0" ]; then
    exec gosu alejandria "$@"
else
    exec "$@"
fi
