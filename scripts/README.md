# Simudza Backup & Restore Scripts

Backup and restore database, media files, and `.env` to/from Google Drive via rclone.

## Prerequisites

- **rclone** configured with a Google Drive remote (default: `gdrive`)
- **Docker** with `simudza_db` and `simudza_media` volumes
- **.env** file in project root with `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD`
- **zip** (for backup) and **unzip** (for restore); install with `apt install zip unzip` on Debian/Ubuntu

## Usage

### Backup

```bash
bash scripts/backup.sh
```

Creates a timestamped zip (e.g. `simudza_20240227_143022.zip`) containing:
- `db.dump` – PostgreSQL dump
- `media/` – Uploaded media files
- `.env` – Environment variables

Uploads to `gdrive:Backups/simudza/` and keeps a maximum of 2 backups (deletes oldest when a 3rd is created).

### Google Drive token (rclone)

rclone stores OAuth tokens in `~/.config/rclone/rclone.conf`. Short-lived access tokens refresh automatically **only while the refresh token is valid**.

| Cause of `invalid_grant` | Fix |
|--------------------------|-----|
| OAuth app in **Testing** mode | [Publish to Production](https://console.cloud.google.com/apis/credentials/consent) (Testing refresh tokens expire after ~7 days) |
| Token revoked / unused 6+ months | Reconnect (below) |
| Client secret rotated | Reconnect with new secret |

**Reconnect after expiry (on VPS):**

```bash
rclone config reconnect gdrive:
# Answer: y
# Complete browser authorization (or paste token from `rclone authorize "drive"` on your laptop)
```

**Weekly health check (optional cron):**

```bash
0 3 * * 0 cd /root/srv/simudza-web && bash scripts/rclone-healthcheck.sh >> rclone-health.log 2>&1
```

### Restore

```bash
# Restore latest backup
bash scripts/restore.sh latest

# Restore specific backup
bash scripts/restore.sh simudza_20240227_143022.zip
```

Prompts for confirmation before restoring database and `.env`.

## Environment Variables

| Variable        | Default   | Description                    |
|----------------|-----------|--------------------------------|
| `RCLONE_REMOTE`| `gdrive`  | rclone remote name             |
| `RCLONE_BASE`  | `Backups` | Root folder for all app backups |
| `APP_NAME`     | `simudza` | App subfolder name             |
| `MAX_BACKUPS`  | `2`       | Max backups to keep per app     |

## Folder Structure

```
Backups/                    # Shared root (multiple apps)
  simudza/                  # This app's backups
    simudza_20240227_143022.zip
    simudza_20240227_020000.zip
```
