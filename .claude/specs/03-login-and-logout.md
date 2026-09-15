# Spec: Login and Logout

## Overview
This step turns the existing `GET /login` page (currently a static template render) into a working sign-in flow, and implements the `/logout` stub. Users submit the form on `login.html`, the server verifies their email/password against the `users` table, and a session is created on success. `/logout` clears that session and returns the user to the landing page. This builds directly on the session pattern established in Step 02 (registration) and is a prerequisite for `/profile` (Step 04), which needs a logged-in session to identify the current user.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`) — present in `database/db.py`.
- Step 02 — Registration (`get_user_by_email()`, session-on-login pattern, `app.secret_key`) — present in `app.py` and `database/db.py`.

## Routes
- `GET /login` — renders the login form — public (already implemented, unchanged)
- `POST /login` — validates credentials, starts a session, redirects to `/` — public
- `GET /logout` — clears the session, redirects to `/` — logged-in (safe no-op if no session exists)

## Database changes
No schema changes. The `users` table already stores `password_hash`, which is sufficient for login verification.

New function needed in `database/db.py` (route logic must not touch SQL directly):
- No new query function is needed for lookup — `get_user_by_email(email)` (from Step 02) already returns the row needed to verify the password hash.

## Templates
- **Create:** none
- **Modify:** `templates/login.html`
  - Change the form's hardcoded `action="/login"` to `action="{{ url_for('login') }}"` (CLAUDE.md forbids hardcoded URLs)
  - Keep the existing `{% if error %}` block for invalid-credential messages — no new markup needed

## Files to change
- `app.py` — add `methods=["GET", "POST"]` to the `/login` route, implement POST handling (look up user by email, verify password with `check_password_hash`, set session, redirect to `/`); implement `/logout` (clear session, redirect to `/`)
- `templates/login.html` — fix hardcoded form action

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is available alongside `generate_password_hash`, already imported from the same module.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`check_password_hash` against the stored `password_hash`, never plaintext comparison)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic inline in `app.py` — all queries go through `database/db.py`
- Never hardcode URLs in templates — use `url_for()`
- Use a single generic error message (e.g. "Invalid email or password") for both unknown email and wrong password — do not reveal which one was incorrect
- Reject invalid credentials by re-rendering `login.html` with the existing `error` template variable, not a raw `abort()`
- Use `abort(400)` only for malformed/missing POST data that indicates a non-form request, not for expected validation failures
- `/logout` must render/redirect properly (per CLAUDE.md: never return a raw string once a stub is implemented) — clear `session["user_id"]` via `session.clear()` or `session.pop("user_id", None)`, then redirect
- `/logout` must not error if called with no active session — just redirect to `/`
- Do not touch `/register` or `/profile` route logic beyond redirecting into them — `/profile` remains a stub owned by Step 04

## Definition of done
- [ ] Submitting the login form with the seeded demo account (`demo@spendly.com` / `demo123`) logs in successfully and redirects to `/`
- [ ] Submitting the login form with a correct email but wrong password re-renders `login.html` with a generic invalid-credentials error and does not create a session
- [ ] Submitting the login form with an email that doesn't exist re-renders `login.html` with the same generic invalid-credentials error (no user enumeration)
- [ ] Submitting with a missing field re-renders `login.html` with an error instead of crashing
- [ ] After logging in, visiting `/logout` clears the session and redirects to `/`
- [ ] Visiting `/logout` with no active session does not error and redirects to `/`
- [ ] The login form's action uses `url_for('login')`, not a hardcoded path
- [ ] `python app.py` starts without errors on port 5001
