# Simudza (simudza-web)

Django + Wagtail registry of Zimbabwean businesses and products (directory, marketplace, verification, reviews).

## Architecture

**Database-first:** the registry lives in PostgreSQL and domain Python; the site, admin, dashboard, email, and cron are surfaces on the same rules. Details in [Commands.md](Commands.md#architecture) and [.claude/rules/database-first-architecture.md](.claude/rules/database-first-architecture.md).

Mirror for Cursor: [.cursor/rules/database-first-architecture.mdc](.cursor/rules/database-first-architecture.mdc).

## Commands

- Run app: `docker compose up`
- Migrate: `docker compose exec -T web python manage.py migrate`
- Tests: `docker compose exec -T web python manage.py test <app_or_module>` — run only tests covering your change; CI runs the full suite ([.claude/rules/targeted-tests.md](.claude/rules/targeted-tests.md), Cursor: [.cursor/rules/targeted-tests.mdc](.cursor/rules/targeted-tests.mdc))
- Ops (dump, restore, verification cron): [Commands.md](Commands.md)

## Domain layout (verification example)

- `businesses/verification.py` — levels, freshness, shared constants
- `businesses/verification_workflow.py` — writes, owner/staff flows, exceptions
- `businesses/verification_dashboard.py` — staff dashboard aggregations
- `businesses/services.py` — submission apply and related side effects

New cross-cutting listing behavior should follow that pattern, not views or templates alone.
