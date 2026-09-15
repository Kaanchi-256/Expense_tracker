# Spec: Registration

## Overview
This step turns the existing `GET /register` page (currently a static template
render) into a working registration flow. Users submit the form on
`register.html`, the server validates and stores their account in the
`users` table with a hashed password, and a session is created so the new
user is signed in immediately. This is the first step in the roadmap that
writes to the database from a route, and it establishes the session pattern
that `/login` and `/logout` will reuse in later steps.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`)
  must already exist. Confirmed present in `database/db.py`.

## Routes
- `GET /register` — renders the registration form — public (already implemented, unchanged)
- `POST /register` — validates input, creates the user, starts a session, redirects to `/profile` — public

## Database changes
No schema changes. The `users` table (`id`, `name`, `email`, `password_hash`,
`created_at`) already supports registration as-is.

New functions needed in `database/db.py` (route logic must not touch SQL directly):
- `get_user_by_email(email)` — parameterized `SELECT` returning a row or `None`, used to check for duplicate emails
- `create_user(name, email, password_hash)` — parameterized `INSERT` into `users`, returns the new user's id

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change the form's hardcoded `action="/register"` to `action="{{ url_for('register') }}"` (CLAUDE.md forbids hardcoded URLs)
  - Keep the existing `{% if error %}` block for validation/duplicate-email messages — no new markup needed

## Files to change
- `app.py` — add `methods=["GET", "POST"]` to the `/register` route, implement POST handling (validate, hash, call `create_user`, set session, redirect), add `app.secret_key`
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — fix hardcoded form action

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` (already used in `database/db.py`) provides `generate_password_hash`; `check_password_hash` is not needed for this step.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic inline in `app.py` — all queries go through `database/db.py`
- Never hardcode URLs in templates — use `url_for()`
- Validate on the server even though the form has `required`/`type=email` HTML attributes (do not trust client-side validation alone)
- Reject duplicate emails with a friendly error re-rendered on `register.html` (via the existing `error` template variable), not a raw `abort()` — this is a user-facing form error, not an HTTP error
- Use `abort(400)` only for malformed/missing POST data that indicates a non-form request, not for expected validation failures
- Do not touch `/login`, `/logout`, or `/profile` route logic beyond redirecting into them — those remain stubs owned by later steps

## Definition of done
- [ ] Submitting the register form with valid, unique name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] After successful registration, the user is redirected to `/login` and a session exists for them
- [ ] Submitting with an email that already exists re-renders `register.html` with an error and does not create a duplicate row
- [ ] Submitting with a missing field re-renders `register.html` with an error instead of crashing
- [ ] The register form's action uses `url_for('register')`, not a hardcoded path
- [ ] `python app.py` starts without errors on port 5001
- [ ] `/seed-user`'s demo account (`demo@spendly.com`) still logs no errors and registering with that same email is correctly rejected as a duplicate
