---
paths:
  - "**/*.html"
---

# Templates: display only

When editing Django/Wagtail templates:

- Use model/context properties (`is_trusted`, `level_meta`, `freshness`, precomputed counts)—do not encode trust, visibility, or verification rules with string comparisons in HTML.
- Prefer shared partials under `simudza/templates/partials/` for badges and status UI.
- If a template needs a new conditional rule, add it in Python (queryset, service, or view context) first, then render the result.
