# Spec: Add Expenses

## Overview
This feature implements the `GET /expenses/add` and `POST /expenses/add` routes, replacing the current stub. It lets a logged-in user record a new expense (amount, category, date, description) through a form, persisting it to the `expenses` table. This is the first of three CRUD steps for expenses (add → edit → delete) and builds directly on the profile page, which already reads from `expenses` via `database/db.py` helpers.

## Depends on
- Step 01 — Database setup (`users`, `expenses` tables exist)
- Step 05 — Wire profile database (`database/db.py` query helpers, `get_db()` pattern)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in
- `POST /expenses/add` — validate and insert a new expense, then redirect to `/profile` — logged-in

Both methods are handled by the existing `add_expense` view (`methods=["GET", "POST"]`), matching the pattern used by `register`/`login`. Unauthenticated requests redirect to `/login`, consistent with `/profile`.

## Database changes
No database changes. The `expenses` table (`database/db.py`, `init_db()`) already has the required columns: `user_id`, `amount`, `category`, `date`, `description`. A new helper function, `create_expense(user_id, amount, category, expense_date, description)`, will be added to `database/db.py` to perform the parameterized `INSERT` — no schema changes needed.

## Templates
- **Create:** `templates/expenses_add.html` — form with fields for amount, category (select, from `CATEGORIES` in `database/db.py`), date, description; extends `base.html`
- **Modify:** none required. (Optional: `templates/profile.html` may already link to `/expenses/add`; no change needed if so — verify during implementation and only touch it if the link is missing.)

## Files to change
- `app.py` — replace the `add_expense` stub with the real `GET`/`POST` implementation
- `database/db.py` — add `create_expense()` helper

## Files to create
- `templates/expenses_add.html`
- `static/css/expenses.css` — page-specific styles for the add-expense form (per CLAUDE.md, page-specific styles get their own CSS file, not inline `<style>`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders)
- Passwords hashed with werkzeug (n/a to this feature, but no regressions to existing auth code)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic only in `database/db.py`, never inline in `app.py`
- Validate `amount` (must parse as a positive number) and `category` (must be one of `CATEGORIES`) server-side before insert; on validation failure, re-render the form with an `error` message and the submitted values preserved
- Use `abort()` for HTTP errors, not bare string returns
- Use `url_for()` for all internal links in templates

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data inserts a row into `expenses` for the current `user_id` and redirects to `/profile`
- [ ] The newly added expense appears in the profile page's recent transactions and category breakdown
- [ ] Submitting with a missing/invalid amount (blank, negative, non-numeric) re-renders the form with an error and no row is inserted
- [ ] Submitting with a category not in `CATEGORIES` re-renders the form with an error and no row is inserted
- [ ] No raw string responses remain for `/expenses/add` — both GET and POST render a template
