# Spec: Edit Expenses

## Overview
This feature implements the `GET /expenses/<id>/edit` route, currently a stub returning a raw string. It lets a logged-in user open an existing expense in a pre-filled form and save changes to its amount, category, date, and description. It builds directly on the expense-creation work from Step 7, reusing the same form layout and validation rules, and moves the expense-tracker roadmap one step closer to full CRUD support for expenses.

## Depends on
- Step 5 — Wire Profile Database (expenses table, `get_db()`, session-based auth)
- Step 7 — Add Expenses (`create_expense`, `CATEGORIES`, `expenses_add.html` layout/validation pattern, `static/css/expenses.css`)

## Routes
- `GET /expenses/<int:id>/edit` — render a pre-filled edit form for the given expense — logged-in
- `POST /expenses/<int:id>/edit` — validate and persist changes to the expense, then redirect to `/profile` — logged-in

Both methods live on the same view function (mirroring `add_expense`), replacing the current stub. If the expense does not exist or does not belong to the logged-in user, respond with `abort(404)`.

## Database changes
No database changes. The `expenses` table (see `database/db.py`) already has all needed columns (`amount`, `category`, `date`, `description`).

New functions needed in `database/db.py` (none exist yet):
- `get_expense_by_id(expense_id)` — `SELECT * FROM expenses WHERE id = ?`, parameterized, returns a row or `None`
- `update_expense(expense_id, amount, category, expense_date, description)` — parameterized `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ?`

Ownership check (`expense["user_id"] == session["user_id"]`) happens in the route, not in `db.py`, matching the pattern of other routes doing auth/session checks.

## Templates
- **Create:** `templates/expenses_edit.html` — edit form, modeled on `templates/expenses_add.html` (same `auth-section`/`auth-card` structure, same `expenses.css` stylesheet), pre-filled with the existing expense's values
- **Modify:** None. `templates/profile.html` already links transactions to `expenses_edit`-style URLs only if it currently has placeholder links — verify during implementation and wire up the edit link via `url_for('edit_expense', expense_id=...)` if not already present.

## Files to change
- `app.py` — replace the `edit_expense` stub with a real `GET`/`POST` view
- `database/db.py` — add `get_expense_by_id()` and `update_expense()`

## Files to create
- `templates/expenses_edit.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable to this feature, but keep in mind repo-wide)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Reuse `CATEGORIES` from `database/db.py` for the category dropdown — do not redefine it
- Validate amount (positive, finite number) and category (must be in `CATEGORIES`) the same way `add_expense` does
- Enforce that a user can only edit their own expenses — `abort(404)` on mismatch or missing row, do not leak existence of other users' expenses via a 403
- Do not touch `GET /expenses/<id>/delete` — that's Step 9, out of scope here

## Definition of done
- [ ] Logged out, visiting `/expenses/1/edit` redirects to `/login`
- [ ] Logged in, visiting `/expenses/<id>/edit` for an expense owned by another user returns a 404
- [ ] Logged in, visiting `/expenses/<id>/edit` for your own expense renders a form pre-filled with its current amount, category, date, and description
- [ ] Submitting the form with a valid amount/category/date updates the expense and redirects to `/profile`
- [ ] Submitting with an invalid amount (blank, zero, negative, non-numeric) re-renders the form with an error and preserves entered values
- [ ] Submitting with a category not in `CATEGORIES` re-renders the form with an error
- [ ] After a successful edit, the updated values are visible in the profile page's transaction list
- [ ] `/expenses/<id>/edit` for a non-existent id returns a 404
