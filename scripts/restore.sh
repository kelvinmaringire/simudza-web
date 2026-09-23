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

REMOTE_PATH="$RCLONE_REMOTE:$RCLONE_BASE/$APP_NAME"
TARGET="${1:-latest}"
TEMP_DIR=".restore_temp_$$"

cleanup() {
  if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
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
  echo "Error: POSTGRES_USER and POSTGRES_DB must be set (ensure .env exists or restore it first)"
  exit 1
fi

if ! command -v unzip &>/dev/null; then
  echo "Error: unzip is required for restore"
  exit 1
fi

ensure_rclone_remote "$RCLONE_REMOTE"

# Resolve backup filename
if [ "$TARGET" = "latest" ]; then
  echo "Finding latest backup..."
  BACKUP_FILE=$(rclone lsl "$REMOTE_PATH/" 2>/dev/null | sort -k2,4 -r | head -n1 | awk '{print $NF}')
  if [ -z "$BACKUP_FILE" ]; then
    echo "Error: No backups found in $REMOTE_PATH"
    exit 1
  fi
  echo "  Using: $BACKUP_FILE"
else
  BACKUP_FILE="$TARGET"
fi

# Download backup
echo "Downloading $BACKUP_FILE..."
mkdir -p "$TEMP_DIR"
rclone copy "$REMOTE_PATH/$BACKUP_FILE" "$TEMP_DIR/"

# Extract
echo "Extracting..."
unzip -q -o "$TEMP_DIR/$BACKUP_FILE" -d "$TEMP_DIR/extracted"
rm -f "$TEMP_DIR/$BACKUP_FILE"

RESTORE_DIR="$TEMP_DIR/extracted"

# Verify extracted contents
if [ ! -f "$RESTORE_DIR/db.dump" ]; then
  echo "Error: Invalid backup - db.dump not found"
  exit 1
fi
if [ ! -d "$RESTORE_DIR/media" ]; then
  echo "Error: Invalid backup - media directory not found"
  exit 1
fi
if [ ! -f "$RESTORE_DIR/.env" ]; then
  echo "Error: Invalid backup - .env not found"
  exit 1
fi

# Database restore
echo ""
echo "  Dropping database..."
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" 2>/dev/null || true
echo "  Creating database..."
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB;"
echo "  Restoring from dump..."
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl < "$RESTORE_DIR/db.dump" 2>/dev/null || true
echo "  Database restored."

# Media restore
echo ""
echo "Restoring media files..."
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q simudza_web; then
  docker compose exec -T web sh -c "rm -rf /app/media/*" 2>/dev/null || true
  docker cp "$RESTORE_DIR/media/." simudza_web:/app/media/
else
  docker run --rm -v simudza_media:/data -v "$PROJECT_ROOT/$TEMP_DIR/extracted/media:/src:ro" alpine sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; cp -a /src/. /data/"
fi
echo "  Media restored."

# .env restore
echo ""
cp "$RESTORE_DIR/.env" .env
echo "  .env restored."

echo ""
echo "Restore complete."
