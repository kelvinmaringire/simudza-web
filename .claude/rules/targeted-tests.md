# Run targeted tests, not the full suite

After making changes, run only the tests that cover the code you touched. Do **not** run the full `python manage.py test` on every change—it slows development, and CI (`.github/workflows/ci.yml`) already runs the full suite on pushes and pull requests to `develop`.

## Picking tests

- Tests live in `<app>/tests.py`, `<app>/test_*.py`, or `<app>/tests/test_*.py`.
- Start with the changed app's tests, narrowed to a module, class, or method when the change is small.
- Add apps that import or depend on what you changed (shared models, `services.py`, `verification*.py`, signals, `simudza/utils/`).
- Changed or added tests: run those directly.
- Template/CSS/JS-only changes with no covering test: skip tests and say so.

## Commands

```bash
# One app
docker compose exec -T web python manage.py test categories

# One module / class / method
docker compose exec -T web python manage.py test businesses.test_verification_workflow
docker compose exec -T web python manage.py test categories.tests.test_hierarchy.CategoryHierarchyTests.test_deep_cycle_rejected

# Several labels at once
docker compose exec -T web python manage.py test categories products marketplace
```

Use `--keepdb` to skip recreating the test database between runs.

## When the full suite is fine

Only run everything when the user asks, or when a change is broad enough that targeting is guesswork (settings, `INSTALLED_APPS`, middleware, base migrations, shared test helpers). Say why when you do.

Never edit `.github/workflows/ci.yml` to change what CI runs.
