# Spec: Delete Expenses

## Overview
This feature implements the `GET /expenses/<id>/delete` route, currently a stub returning a raw string. It lets a logged-in user permanently remove one of their own expenses, completing the CRUD set for expenses (create in Step 7, edit in Step 8, delete here). Deletion is destructive and irreversible, so it requires an explicit confirmation step rather than deleting on a single GET request — this also keeps the delete action safe from being triggered by crawlers, browser prefetch, or an accidental click, since a plain `GET` link that mutates data is not idempotent-safe.

## Depends on
- Step 5 — Wire Profile Database (expenses table, `get_db()`, session-based auth)
- Step 8 — Edit Expenses (`get_expense_by_id(expense_id, user_id)` ownership-filtered lookup, `templates/expenses_edit.html` confirmation-page-adjacent layout, the profile page's per-row Actions dropdown menu)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the expense's details — logged-in
- `POST /expenses/<int:id>/delete` — permanently delete the expense, then redirect to `/profile` — logged-in

Both methods live on the same view function, replacing the current stub. If the expense does not exist or does not belong to the logged-in user, respond with `abort(404)` (matching Step 8's pattern of not leaking existence via a 403).

## Database changes
No schema changes. The `expenses` table already supports deletion by `id`.

New function needed in `database/db.py` (none exists yet):
- `delete_expense(expense_id)` — parameterized `DELETE FROM expenses WHERE id = ?`

Ownership check (`expense["user_id"] == session["user_id"]`) happens in the route via the existing `get_expense_by_id(expense_id, user_id)` (already filters by `user_id` in-query, per Step 8), not in a new db.py function — matching the established pattern.

## Templates
- **Create:** `templates/expenses_delete.html` — confirmation page, styled consistently with `expenses_edit.html`'s `auth-section`/`auth-card` structure, showing the expense's date, category, amount, and description as read-only summary text, with a "Delete" submit button (styled as a destructive action, e.g. using the existing `--danger` CSS variable) and a "Cancel" link back to `/profile`
- **Modify:** `templates/profile.html` — add a "Delete" item to the existing per-row Actions dropdown menu (`.actions-menu-panel`, introduced in Step 8), alongside "Edit", linking to `url_for('delete_expense', id=t.id)`

## Files to change
- `app.py` — replace the `delete_expense` stub with a real `GET`/`POST` view
- `database/db.py` — add `delete_expense()`
- `templates/profile.html` — add "Delete" item to the Actions dropdown

## Files to create
- `templates/expenses_delete.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable to this feature, but keep in mind repo-wide)
- Use CSS variables — never hardcode hex values (use `--danger`/`--danger-light` for the destructive-action styling)
- All templates extend `base.html`
- Enforce that a user can only delete their own expenses — reuse `get_expense_by_id(expense_id, user_id)` from Step 8, `abort(404)` on mismatch or missing row
- Deletion must require a `POST` (confirmed via the confirmation page's form) — a bare `GET` to `/expenses/<id>/delete` must only render the confirmation page and must NOT delete anything
- Reuse the existing `.actions-menu`/`.actions-menu-panel` dropdown component and vanilla JS from Step 8 (`static/js/main.js`, `static/css/profile.css`) — do not introduce a new dropdown implementation
- Do not touch `GET/POST /expenses/<id>/edit` — that's already implemented, out of scope here

## Definition of done
- [ ] Logged out, visiting `/expenses/1/delete` redirects to `/login`
- [ ] Logged in, visiting `/expenses/<id>/delete` for an expense owned by another user returns a 404
- [ ] Logged in, visiting `/expenses/<id>/delete` for a non-existent id returns a 404
- [ ] Logged in, visiting `/expenses/<id>/delete` for your own expense renders a confirmation page showing that expense's date, category, amount, and description
- [ ] A plain GET to the confirmation page does not delete the expense — reloading it repeatedly leaves the expense untouched
- [ ] Submitting the confirmation form (POST) deletes the expense and redirects to `/profile`
- [ ] After deletion, the expense no longer appears in the profile page's transaction list, and profile stats (total spent, transaction count, top category) reflect its removal
- [ ] The "Cancel" link on the confirmation page returns to `/profile` without deleting anything
- [ ] The profile page's Actions dropdown shows both "Edit" and "Delete" for every transaction row
