#!/usr/bin/env bash
# Lightweight rclone token check — run weekly from cron to catch expiry early.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=rclone-common.sh
source "$SCRIPT_DIR/rclone-common.sh"

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"

echo "$(date -Is) Checking ${RCLONE_REMOTE}..."
ensure_rclone_remote "$RCLONE_REMOTE"
echo "$(date -Is) OK: ${RCLONE_REMOTE} token is valid."
