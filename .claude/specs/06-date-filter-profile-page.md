# Spec: Date Filter For Profile Page

## Overview
This feature adds a date-range filter to the profile page, letting a logged-in user narrow the "Recent transactions" list and "Category breakdown" to a specific time window instead of always showing all-time data. The filter UI has two parts: a row of quick-select preset pills (**All Time**, **This Month**, **Last 3 Months**, **Last 6 Months**) for one-click filtering, and a custom date-range picker (start date, end date, **Apply** button) for an arbitrary range. Whichever preset (or custom range) is currently active is visually highlighted. It builds directly on the profile page wired to the database in Step 5, and moves Spendly closer to a fully interactive dashboard before expense CRUD (add/edit/delete) is implemented in Steps 7–9.

## Depends on
- Step 04 — Profile page (template and layout)
- Step 05 — Wire profile database (`get_recent_transactions`, `get_user_stats`, `get_category_breakdown`, and the `/profile` route)

## Routes
- `GET /profile` — modify existing route to accept optional `start_date` and `end_date` query string parameters (`YYYY-MM-DD`) and pass the filtered range down to stats, transactions, and category breakdown; also compute the three preset date ranges (This Month, Last 3 Months, Last 6 Months) relative to today and determine which preset (if any) matches the current filter, for highlighting — access level: logged-in

No new routes are created; the existing `/profile` route is extended to read filter parameters from `request.args`. Preset pills are plain `GET` links to `/profile` with `start_date`/`end_date` query parameters computed server-side — no new endpoints or JS-driven requests are needed.

## Database changes
No database changes. `database/db.py` already stores `date` as a `TEXT` column in `ISO 8601` (`YYYY-MM-DD`) format on `expenses`, which sorts and compares correctly with `?` bound parameters in `BETWEEN`/`>=`/`<=` clauses. No new tables, columns, or constraints are needed.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — add a filter bar above the "Recent transactions" / "Category breakdown" columns, containing:
  - Four preset pills (`All Time`, `This Month`, `Last 3 Months`, `Last 6 Months`) rendered as links to `/profile` with the appropriate `start_date`/`end_date` (or no params for `All Time`); the pill matching the currently active filter is styled as selected
  - A custom range sub-form (`method="get"`) with a start-date input, an end-date input, and an **Apply** submit button, styled as pills/inputs consistent with the preset row
  - Preserve selected custom-range values in the date inputs after submit
  - Show a "No transactions in this range" message when the filtered transaction list is empty, and a matching empty message under "Category breakdown"

The previous "Clear" link is replaced by the **All Time** preset pill, which serves the same purpose (returns to `/profile` with no filters).

## Files to change
- `app.py` — update the `profile()` route to read `start_date`/`end_date` from `request.args`, validate them, compute the three preset ranges and which one (if any) is active, and pass everything through to the `database/db.py` query functions and the template
- `database/db.py` — update `get_recent_transactions`, `get_user_stats`, and `get_category_breakdown` to accept optional `start_date`/`end_date` parameters and apply a parameterized date filter when present
- `templates/profile.html` — add the preset pill row, the custom range sub-form, and empty-state messages
- `static/css/profile.css` — add styles for the filter bar, preset pills (default and active states), and the custom range sub-form, using existing CSS variables

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or string concatenation, including for the date filter clause
- Passwords hashed with werkzeug (unaffected by this feature, but remains a standing rule)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate `start_date`/`end_date` server-side (must parse as valid `YYYY-MM-DD` dates); on invalid input, ignore the filter and fall back to unfiltered data rather than raising a 500
- If only one of `start_date`/`end_date` is supplied, treat it as an open-ended range (from that date onward, or up to that date)
- DB logic (date filtering, query construction) stays in `database/db.py` — never inline SQL in `app.py`
- Never hardcode URLs in the template — use `url_for()` for the preset pill links, the custom-range form action, and any other internal link
- Preset date ranges (This Month, Last 3 Months, Last 6 Months) are computed server-side in `app.py` using only the standard library (`datetime`/`date`/`calendar`) — no new pip packages (e.g. `python-dateutil`) for date math
- "This Month" = the 1st of the current month through today; "Last 3/6 Months" = a rolling window from N calendar months before today through today
- The route determines which single preset (if any) matches the current `start_date`/`end_date` and passes that to the template so exactly one pill (or none, for a non-matching custom range) is shown as active — this logic belongs in `app.py`, not duplicated in the template

## Definition of done
- [ ] Visiting `/profile` with no query parameters shows all-time data exactly as before, and the "All Time" pill is shown as active (no regression)
- [ ] Clicking "This Month" filters to the 1st of the current month through today, and the "This Month" pill is shown as active
- [ ] Clicking "Last 3 Months" / "Last 6 Months" filters to the corresponding rolling window ending today, and the matching pill is shown as active
- [ ] Submitting the custom range form (via "Apply") with a valid start and end date shows only transactions within that range in "Recent transactions"
- [ ] "Category breakdown" and the stat tiles (total spent, transaction count, top category) update to reflect the same filtered range, regardless of whether the range came from a preset pill or the custom form
- [ ] Submitting only a start date filters to that date and later; submitting only an end date filters up to that date
- [ ] Selected custom-range values remain populated in the date inputs after the page reloads
- [ ] Clicking "All Time" returns to `/profile` with no filters and full data restored
- [ ] Filtering to a range with no matching transactions shows an empty-state message instead of an empty table or an error
- [ ] Submitting a malformed date (e.g. via manually edited URL query string) does not crash the app — it falls back to unfiltered data
- [ ] A custom range that happens to exactly match a preset's computed range shows that preset pill as active; a custom range that matches none of the presets shows no pill as active
- [ ] All SQL queries touching the date filter use `?` placeholders, verified by reading `database/db.py`
