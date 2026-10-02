# Architecture

**Database-first:** Simudza is a registry database with surfaces (public site, marketplace, owner/staff dashboard, Wagtail admin, emails, cron). Do not build a website that happens to have a database.

- **Truth:** PostgreSQL schema (fields, defaults, migrations).
- **Rules:** Python domain layer—`services.py`, `verification.py`, `verification_workflow.py`, `verification_dashboard.py`, model querysets (e.g. `visible_in_search()`).
- **Surfaces:** Templates and views render and collect input; they call domain code and display properties like `level_meta`, `is_trusted`, `freshness`—no duplicated trust/visibility logic in HTML.

When adding behavior, ask: *would a second client (API, export, job) use the same function without copying template `if` blocks?* If not, push logic down.

- **Cursor:** `.cursor/rules/database-first-architecture.mdc` (`alwaysApply`)
- **Claude Code:** `CLAUDE.md`, `.claude/rules/database-first-architecture.md`, and `.claude/rules/templates-no-business-logic.md` (HTML paths)

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

# Admin import / export (Wagtail `/admin/`)

Each registry list (Businesses, Products, Categories, Directory, Inventory, Marketplace orders/carts/checkouts, Reviews, Users) has **Import CSV**, **Import Excel**, **Export CSV**, and **Export Excel** in the header actions menu (⋯).

- Upload shows a **dry-run preview** (new / update / skip / errors) before you confirm.
- **Business** and **Product** rows match on `slug` for updates.
- **User** import never includes passwords; new users get an unusable password until reset.
- Importing **orders** or **carts** does not run checkout, payment, or stock workflows — line items appear in export as a read-only `items` column only.

# Verification monitor (run daily)

Emails owners whose listings are older than 90 days (at most once every 30 days) and prints how many exceptions staff need to handle.

```bash
docker compose exec -T web python manage.py monitor_verification --dry-run
docker compose exec -T web python manage.py monitor_verification
```

Cron on the server (06:00 daily):

```cron
0 6 * * * cd /root/srv/simudza-web && docker compose exec -T web python manage.py monitor_verification >> /var/log/simudza-monitor.log 2>&1
```

Recompute data-quality scores (verification age and other time-based checks):

```bash
docker compose exec -T web python manage.py refresh_data_quality --dry-run
docker compose exec -T web python manage.py refresh_data_quality
```

Cron (06:15 daily, after verification monitor):

```cron
15 6 * * * cd /root/srv/simudza-web && docker compose exec -T web python manage.py refresh_data_quality >> /var/log/simudza-quality.log 2>&1
```

# Duplicate detection

Businesses and products are checked automatically on save. Possible duplicates are **flagged for review** under **Possible duplicates** in `/admin/` — listings are never edited or deleted automatically. "Not a duplicate" decisions are remembered; a dismissed pair is only reopened if a new hard identifier (barcode, SKU, website, email, phone) starts matching.

Re-check everything (after imports, or nightly):

```bash
docker compose exec -T web python manage.py scan_duplicates
docker compose exec -T web python manage.py scan_duplicates --products-only
```
