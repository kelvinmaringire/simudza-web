# Database-first architecture

**Principle:** Build Simudza as a database that happens to have a website—not a website that happens to have a database.

The product is the registry (businesses, products, verification, directory, reviews). Public pages, marketplace, accounts dashboard, Wagtail admin, emails, and management commands are **views on the same data and rules**.

## Where logic belongs

| Layer | Responsibility |
|-------|----------------|
| **Models + migrations** | Fields, defaults, constraints, indexes; `@property` that only combine model fields |
| **Querysets** | Reusable visibility/filter rules (e.g. `visible_in_search()`) |
| **`services.py`, `verification*.py`, `*_workflow.py`** | Writes, workflows, cross-model rules, side effects |
| **Views / viewsets** | Auth, HTTP, orchestration—call domain functions; avoid duplicating filter rules |
| **Templates** | Display `level_meta`, `is_trusted`, counts from context—**no business rules** |

## Do

- Add new listing states as model fields + migration + domain helpers (shared enums in `businesses/verification.py`).
- Route all writes through one path (e.g. `mark_verified`, `apply_submission`, `staff_set_level`).
- Share filters via constants/querysets (`TRUSTED_LEVELS`, `visible_in_search()`), not copy-paste in marketplace/directory/views.

## Avoid

- `{% if ... == "verified" %}` or magic strings for trust/visibility in templates.
- Views that set many related fields without going through workflow/services.
- Cron or dashboard logic that reimplements rules already in workflow modules.

## Sanity check

Could a CSV export or new API reuse the same models and workflow without copying template conditionals? If not, move the rule down into models/services/querysets.
