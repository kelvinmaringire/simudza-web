#!/usr/bin/env bash
set -e

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# shellcheck source=rclone-common.sh
source "$SCRIPT_DIR/rclone-common.sh"

# Configuration (override via env)
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_BASE="${RCLONE_BASE:-Backups}"
APP_NAME="${APP_NAME:-simudza}"
MAX_BACKUPS="${MAX_BACKUPS:-2}"

REMOTE_PATH="$RCLONE_REMOTE:$RCLONE_BASE/$APP_NAME"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TEMP_DIR=".backup_temp_$TIMESTAMP"
BACKUP_ZIP="${APP_NAME}_${TIMESTAMP}.zip"

cleanup() {
  if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
  fi
  if [ -f "$BACKUP_ZIP" ]; then
    rm -f "$BACKUP_ZIP"
  fi
}
trap cleanup EXIT

# Load .env for database credentials (strip CR for Windows-edited files)
# Parse line-by-line to avoid shell syntax errors from special chars (e.g. parens in values)
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "$line" ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
    fi
  done < .env
fi

if [ -z "${POSTGRES_USER:-}" ] || [ -z "${POSTGRES_DB:-}" ]; then
  echo "Error: POSTGRES_USER and POSTGRES_DB must be set (from .env)"
  exit 1
fi

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q simudza_db; then
  echo "Error: simudza_db container must be running for database backup"
  exit 1
fi

if ! command -v zip &>/dev/null; then
  echo "Error: zip is required for backup (apt install zip)"
  exit 1
fi

echo "Creating backup: $BACKUP_ZIP"
mkdir -p "$TEMP_DIR"

# 1. Database dump
echo "  - Dumping database..."
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c > "$TEMP_DIR/db.dump"

# 2. Media files (use web container if running, else volume directly)
echo "  - Copying media files..."
mkdir -p "$TEMP_DIR/media"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q simudza_web; then
  docker cp simudza_web:/app/media/. "$TEMP_DIR/media/"
else
  docker run --rm -v simudza_media:/data -v "$PROJECT_ROOT/$TEMP_DIR/media:/out" alpine sh -c "cp -a /data/. /out/"
fi

# 3. .env file
echo "  - Copying .env..."
cp .env "$TEMP_DIR/.env"

# 4. Create zip archive
echo "  - Creating archive..."
cd "$TEMP_DIR"
zip -rq "../$BACKUP_ZIP" .
cd "$PROJECT_ROOT"

# 5. Verify Google Drive token (auto-refreshes access token when refresh token is valid)
ensure_rclone_remote "$RCLONE_REMOTE"

# 6. Ensure remote path exists
echo "  - Ensuring remote path exists..."
rclone mkdir "$REMOTE_PATH" 2>/dev/null || true

# 7. Upload
echo "  - Uploading to $REMOTE_PATH..."
rclone copy "$BACKUP_ZIP" "$REMOTE_PATH/"

# 8. Retention: keep max MAX_BACKUPS, delete oldest
echo "  - Applying retention (max $MAX_BACKUPS backups)..."
BACKUP_LIST=$(rclone lsl "$REMOTE_PATH/" 2>/dev/null | sort -k2,4 | awk '{print $NF}' || true)
COUNT=$(echo "$BACKUP_LIST" | grep -c . 2>/dev/null || echo "0")

if [ "$COUNT" -gt "$MAX_BACKUPS" ]; then
  TO_DELETE=$((COUNT - MAX_BACKUPS))
  echo "$BACKUP_LIST" | head -n "$TO_DELETE" | while read -r file; do
    if [ -n "$file" ]; then
      echo "    Deleting oldest: $file"
      rclone delete "$REMOTE_PATH/$file" 2>/dev/null || true
    fi
  done
fi

echo "Backup complete: $REMOTE_PATH/$BACKUP_ZIP"
