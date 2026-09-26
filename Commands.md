# Typography

Default app font: **Geist** (single family, light + dark).

- Google Fonts: https://fonts.google.com/specimen/Geist
- Loaded in `simudza/templates/base.html`
- Applied via `--default-font-family` / `--font-sans` in `simudza/static/css/theme.css`
- Weights in use: 400, 500, 600, 700

# Database dump (custom format)

```bash
docker compose exec -T db pg_dump -U postgres -d simudza_db -F c > simudza_db.dump
```

# Media out of the web container (or volume)

```bash
mkdir -p media_export
docker cp simudza_web:/app/media/. media_export/
```

# Restore on the server

```bash
cd /root/srv/simudza-web
```

## Restore DB (destructive — replaces the DB)

```bash
docker compose exec -T db psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS simudza_db;"
docker compose exec -T db psql -U postgres -d postgres -c "CREATE DATABASE simudza_db;"
docker compose exec -T db pg_restore -U postgres -d simudza_db --no-owner --no-acl < simudza_db.dump
```

## Restore media into the web container

```bash
docker compose exec -T web sh -c "rm -rf /app/media/*"
docker cp media_export/. simudza_web:/app/media/
```
